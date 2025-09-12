import asyncio
import base64
import json
import os
import pprint
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import construct
import nacl.signing
from anchorpy import Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from solders.instruction import Instruction
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from websockets.client import WebSocketClientProtocol, connect
from websockets.exceptions import ConnectionClosed, WebSocketException

from driftpy.accounts import get_user_stats_account_public_key
from driftpy.addresses import get_user_account_public_key
from driftpy.drift_client import DriftClient
from driftpy.keypair import load_keypair
from driftpy.math.orders import standardize_price
from driftpy.swift.order_subscriber import SIGNED_MSG_DELEGATE_DISCRIMINATOR
from driftpy.types import (
    MarketType,
    OrderParams,
    OrderParamsBitFlag,
    OrderTriggerCondition,
    OrderType,
    PositionDirection,
    PostOnlyParams,
    SignedMsgOrderParams,
    is_variant,
)
from driftpy.user_map.referrer_map import ReferrerMap
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import PollingConfig, UserMapConfig

pp = pprint.PrettyPrinter(indent=2)


@dataclass
class RuntimeSpec:
    drift_env: str = "mainnet"


class SwiftMaker:
    def __init__(
        self,
        drift_client: DriftClient,
        user_map: UserMap,
        runtime_spec: RuntimeSpec,
        auth_keypair: Keypair,  # Keypair specifically for WS authentication
        stake_keypair: Optional[Keypair] = None,  # Optional keypair for staking rewards
        markets_to_subscribe: List[str] = ["SOL-PERP"],
        dry_run: bool = False,
    ):
        self.drift_client: DriftClient = drift_client
        self.user_map: UserMap = user_map
        self.runtime_spec: RuntimeSpec = runtime_spec
        self.auth_keypair: Keypair = auth_keypair
        self.stake_keypair: Optional[Keypair] = stake_keypair
        self.markets_to_subscribe: List[str] = markets_to_subscribe
        self.dry_run: bool = dry_run

        self.ws: Optional[WebSocketClientProtocol] = None
        self.ws_endpoint = self._get_ws_endpoint()
        self.is_connected = False
        self.is_authenticated = False
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.last_heartbeat_ts: float = 0
        self.heartbeat_interval_s = 20  # Send pings more often
        self.heartbeat_timeout_s = 80  # Reconnect if no pong/message received
        self.referrer_map: ReferrerMap = ReferrerMap(
            self.drift_client, parallel_sync=True, verbose=False
        )

    def _get_ws_endpoint(self) -> str:
        if self.runtime_spec.drift_env == "mainnet":
            return "wss://swift.drift.trade/ws"
        elif self.runtime_spec.drift_env == "devnet":
            return "wss://master.swift.drift.trade/ws"
        else:
            raise ValueError(f"Unsupported drift_env: {self.runtime_spec.drift_env}")

    async def init(self):
        begin_time = time.time()
        print("Subscribing DriftClient...")
        await self.drift_client.subscribe()
        print("DriftClient subscribed.")
        print("Subscribing UserMap...")
        await self.user_map.subscribe()
        print("UserMap subscribed.")
        print("Subscribing ReferrerMap...")
        await self.referrer_map.subscribe()
        print("ReferrerMap subscribed.")
        print(f"SwiftMaker init() took: {time.time() - begin_time:.2f}s")
        print("Initializing SwiftMaker...")
        asyncio.create_task(self.subscribe_ws())

    def _start_heartbeat_check(self):
        """Starts a task to monitor heartbeat responses."""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()

        async def _heartbeat_monitor():
            while self.is_connected:
                await asyncio.sleep(self.heartbeat_timeout_s)
                now = time.time()
                if now - self.last_heartbeat_ts > self.heartbeat_timeout_s:
                    print(
                        f"Heartbeat timeout ({self.heartbeat_timeout_s}s). Last received: {self.last_heartbeat_ts:.2f}. Reconnecting..."
                    )
                    asyncio.create_task(self._reconnect())
                    break  # Exit monitor task on timeout/reconnect attempt

        print("Starting heartbeat monitor task.")
        self.last_heartbeat_ts = time.time()  # Reset timestamp on start
        self.heartbeat_task = asyncio.create_task(_heartbeat_monitor())

    async def _reconnect(self):
        print("Attempting to reconnect...")
        self.is_connected = False
        self.is_authenticated = False
        if self.ws:
            try:
                await self.ws.close()
            except WebSocketException as e:
                print(f"Error closing websocket during reconnect: {e}")
            self.ws = None
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None

        # Exponential backoff could be added here
        await asyncio.sleep(5)  # Wait before trying to reconnect
        await self.subscribe_ws()

    async def subscribe_ws(self):
        """Establishes WebSocket connection, handles authentication, and processes messages."""
        connect_url = f"{self.ws_endpoint}?pubkey={str(self.auth_keypair.pubkey())}"
        print(f"Connecting to WebSocket: {connect_url}")

        try:
            async with connect(
                connect_url,
                open_timeout=60,
                ping_interval=self.heartbeat_interval_s,
                ping_timeout=30,
            ) as websocket:
                self.ws = websocket
                self.is_connected = True
                self.is_authenticated = False
                print("WebSocket connection established.")
                self._start_heartbeat_check()

                async for raw_message in websocket:
                    self.last_heartbeat_ts = time.time()

                    try:
                        message = json.loads(raw_message)
                        await self._process_message(message)
                    except json.JSONDecodeError:
                        print(f"Received non-JSON message: {raw_message}")
                    except Exception as e:
                        print(f"Error processing message: {e}")

        except (
            ConnectionClosed,
            WebSocketException,
            asyncio.TimeoutError,
            OSError,
        ) as e:
            print(f"WebSocket connection error: {e}. Attempting reconnect...")
            self.is_connected = False
            self.is_authenticated = False
            await self._reconnect()
        except Exception as e:
            print(f"Unexpected error in subscribe_ws: {e}")
            self.is_connected = False
            self.is_authenticated = False
            await self._reconnect()  # Attempt reconnect on unexpected errors too

    async def _process_message(self, message: Dict):
        """Processes incoming WebSocket messages."""
        channel = message.get("channel")
        msg_type = message.get("message")

        if channel == "auth":
            if "nonce" in message:
                await self._handle_auth_challenge(message["nonce"])
            elif isinstance(msg_type, str) and msg_type == "Authenticated":
                print("WebSocket successfully authenticated.")
                self.is_authenticated = True
                await self._subscribe_to_markets()
            elif isinstance(msg_type, str):
                print(f"Received auth message: {msg_type}")

        elif "order" in message and self.is_authenticated:
            if self.user_map.is_subscribed:
                asyncio.create_task(self._handle_order(message["order"]))
            else:
                print(
                    "Received order message but DriftClient/UserMap not ready. Skipping."
                )

        elif channel == "heartbeat":
            pass

        else:
            print(f"Received unhandled message: {pp.pformat(message)}")

    async def _handle_auth_challenge(self, nonce: str):
        """Signs the auth nonce and sends it back."""
        if not self.ws:
            print("Cannot handle auth challenge, WebSocket is not connected.")
            return

        print("Received auth challenge, signing nonce...")
        message_bytes = nonce.encode("utf-8")
        signing_key = nacl.signing.SigningKey(self.auth_keypair.secret())
        signature = signing_key.sign(message_bytes).signature
        signature_b64 = base64.b64encode(signature).decode("utf-8")

        auth_payload = {
            "pubkey": str(self.auth_keypair.pubkey()),
            "signature": signature_b64,
        }
        if self.stake_keypair:
            auth_payload["stake_pubkey"] = str(self.stake_keypair.pubkey())

        try:
            await self.ws.send(json.dumps(auth_payload))
            print("Sent authentication response.")
        except WebSocketException as e:
            print(f"Failed to send authentication response: {e}")

    async def _subscribe_to_markets(self):
        """Sends subscription requests for the configured markets."""
        if not self.ws or not self.is_authenticated:
            print(
                "Cannot subscribe to markets, WebSocket not connected or authenticated."
            )
            return

        print(f"Subscribing to markets: {self.markets_to_subscribe}")
        for market_name in self.markets_to_subscribe:
            sub_payload = {
                "action": "subscribe",
                "market_type": "perp",
                "market_name": market_name,
            }
            try:
                await self.ws.send(json.dumps(sub_payload))
                print(f"Sent subscription request for {market_name}")
                await asyncio.sleep(0.1)
                print(f"Subscribed to {market_name}")
            except WebSocketException as e:
                print(f"Failed to send subscription for {market_name}: {e}")

    async def _handle_order(self, order_message_raw: Dict):
        """Processes a received order, generates maker instructions, and potentially sends the transaction."""
        order_received_ts = time.time()
        order_uuid_str = order_message_raw.get("uuid", "unknown_uuid")
        print(f"Handling order {order_uuid_str} received at {order_received_ts:.3f}")

        try:
            signed_msg_order_params_buf_hex = order_message_raw["order_message"]
            signed_msg_order_params_buf = bytes.fromhex(signed_msg_order_params_buf_hex)
            signed_msg_order_params_buf_utf8_style = order_message_raw[
                "order_message"
            ].encode("utf-8")

            print(
                f"Order {order_uuid_str}: ORDER_MESSAGE_UTF8_STYLE: {signed_msg_order_params_buf_utf8_style}"
            )
            taker_signature_b64 = order_message_raw["order_signature"]
            print(f"Order {order_uuid_str}: TAKER_SIGNATURE_B64: {taker_signature_b64}")
            taker_signature = base64.b64decode(taker_signature_b64)
            order_uuid = order_uuid_str.encode("utf-8")

            print(
                f"Order {order_uuid_str}: Raw buffer hex: {signed_msg_order_params_buf.hex()}"
            )

            is_delegate = False
            is_delegate_signer = (
                signed_msg_order_params_buf[:8] == SIGNED_MSG_DELEGATE_DISCRIMINATOR
            )
            try:
                signed_message = (
                    self.drift_client.decode_signed_msg_order_params_message(
                        signed_msg_order_params_buf, is_delegate=is_delegate_signer
                    )
                )
                is_delegate = is_delegate_signer
            except construct.core.StreamError as e:
                print(
                    f"Order {order_uuid_str}: Failed delegate decode check ({e}), attempting opposite direction."
                )
                try:
                    signed_message = (
                        self.drift_client.decode_signed_msg_order_params_message(
                            signed_msg_order_params_buf,
                            is_delegate=not is_delegate_signer,
                        )
                    )
                    is_delegate = not is_delegate_signer
                except construct.core.StreamError as e:
                    print(
                        f"Failed to decode order message ({order_uuid_str}) as non-delegate either: {e}"
                    )
                    print(
                        f"  Buffer (len={len(signed_msg_order_params_buf)}): {signed_msg_order_params_buf.hex()}"
                    )
                    return

            print(f"=======> Order {order_uuid_str}: is_delegate={is_delegate}")

            taker_order_params: OrderParams = signed_message.signed_msg_order_params
            market_index = taker_order_params.market_index

            if (
                not taker_order_params.price
                and taker_order_params.auction_duration == 0
            ):
                print(
                    f"Order {order_uuid_str} has no price/auction params. Could be an Oracle offset order, in that case you'd calculate the maker price relative to the oracle price."
                )
                return

            taker_authority = Pubkey.from_string(order_message_raw["taker_authority"])
            signing_authority = Pubkey.from_string(
                order_message_raw.get("signing_authority", str(taker_authority))
            )

            if is_delegate:
                taker_user_pubkey = signed_message.taker_pubkey
            else:
                taker_user_pubkey = get_user_account_public_key(
                    self.drift_client.program.program_id,
                    taker_authority,
                    signed_message.sub_account_id,
                )

            taker_user_map_entry = await self.user_map.must_get(str(taker_user_pubkey))
            if not taker_user_map_entry:
                print(
                    f"Could not find taker user account in UserMap: {taker_user_pubkey}"
                )
                return
            taker_user_account = taker_user_map_entry.get_user_account()
            taker_stats_pubkey = get_user_stats_account_public_key(
                self.drift_client.program.program_id, taker_user_account.authority
            )
            perp_market = self.drift_client.get_perp_market_account(market_index)
            is_taker_long = is_variant(taker_order_params.direction, "Long")
            maker_direction = (
                PositionDirection.Short() if is_taker_long else PositionDirection.Long()
            )

            maker_base_amount = perp_market.amm.min_order_size * 2

            if maker_base_amount == 0:
                print(
                    f"Maker base amount is zero for order {order_uuid_str}. Skipping."
                )
                return

            print(
                f"Order {order_uuid_str}: Taker params price={taker_order_params.price}, order_type={taker_order_params.order_type}, "
                f"auction_start={taker_order_params.auction_start_price}, "
                f"auction_end={taker_order_params.auction_end_price}, "
                f"auction_duration={taker_order_params.auction_duration}"
            )

            maker_price = None

            # Oracle offset orders: price == 0 and order_type == Oracle, auction_* are offsets from oracle
            is_oracle_offset = is_variant(taker_order_params.order_type, "Oracle")
            if is_oracle_offset:
                oracle_price_data = (
                    self.drift_client.get_oracle_price_data_for_perp_market(
                        market_index
                    )
                )
                if oracle_price_data is None:
                    print(
                        f"Order {order_uuid_str}: No oracle price available for market {market_index}. Skipping."
                    )
                    return
                oracle_price = oracle_price_data.price
                if is_taker_long:
                    ref_offset = (
                        taker_order_params.auction_end_price
                        if taker_order_params.auction_end_price is not None
                        else (taker_order_params.auction_start_price or 0)
                    )
                    base_price = oracle_price + ref_offset
                    maker_price = (base_price * 101) // 100
                else:
                    ref_offset = (
                        taker_order_params.auction_start_price
                        if taker_order_params.auction_start_price is not None
                        else (taker_order_params.auction_end_price or 0)
                    )
                    base_price = oracle_price + ref_offset
                    maker_price = (base_price * 99) // 100
                maker_price = standardize_price(
                    maker_price, perp_market.amm.order_tick_size, maker_direction
                )
            else:
                if taker_order_params.auction_start_price is not None:
                    maker_price = taker_order_params.auction_start_price
                elif (
                    taker_order_params.price is not None
                    and taker_order_params.price > 0
                ):
                    maker_price = taker_order_params.price

            if maker_price is None or maker_price <= 0:
                print(
                    f"Order {order_uuid_str}: Could not determine valid maker price. Taker Params: Price={taker_order_params.price}, AuctionStart={taker_order_params.auction_start_price}, AuctionEnd={taker_order_params.auction_end_price}. Skipping."
                )
                if is_oracle_offset:
                    print(
                        "This is an Oracle offset order; failed to compute oracle-derived price (missing oracle?)."
                    )
                return

            maker_order_params = OrderParams(
                market_index=market_index,
                order_type=OrderType.Limit(),
                market_type=MarketType.Perp(),
                direction=maker_direction,
                base_asset_amount=maker_base_amount,
                price=maker_price,
                post_only=PostOnlyParams.MustPostOnly(),
                user_order_id=1,
                reduce_only=False,
                trigger_price=None,
                trigger_condition=OrderTriggerCondition.Above(),
                auction_start_price=None,
                auction_end_price=None,
                auction_duration=None,
                max_ts=None,
                oracle_price_offset=None,
                bit_flags=OrderParamsBitFlag.IMMEDIATE_OR_CANCEL,
            )

            taker_info = {
                "taker": taker_user_pubkey,
                "taker_user_account": taker_user_account,
                "taker_stats": taker_stats_pubkey,
                "signing_authority": signing_authority,
            }

            print(f"Constructing place_and_make IXs for order {order_uuid_str}")
            preceding_ixs = [
                set_compute_unit_limit(1_000_000),
                set_compute_unit_price(50_000),
            ]

            referrer_info = None
            try:
                referrer_info = await self.referrer_map.must_get(str(taker_authority))
            except Exception as e:
                print(f"Failed to get referrer info for order {order_uuid_str}: {e}")

            if referrer_info is not None:
                print(
                    f"(Has referrer) Order {order_uuid_str}: Referrer info: {referrer_info}"
                )

            order_params_buf = SignedMsgOrderParams(
                order_params=signed_msg_order_params_buf_utf8_style,
                signature=taker_signature,
            )

            fill_ixs = (
                await self.drift_client.get_place_and_make_signed_msg_perp_order_ixs(
                    signed_msg_order_params=order_params_buf,
                    signed_msg_order_uuid=order_uuid,
                    taker_info=taker_info,
                    order_params=maker_order_params,
                    preceding_ixs=preceding_ixs,
                    referrer_info=referrer_info,
                )
            )

            print(
                f"Order {order_uuid_str}: Calculated maker_price={maker_order_params.price}"
            )

            all_ixs = fill_ixs
            print(
                f"Generated {len(fill_ixs)} fill instructions for order {order_uuid_str}."
            )

            if self.dry_run:
                all_ixs.append(order_uuid_str)
                with open("py_orders.log", "a") as f:
                    f.write(f"{all_ixs}\n")
                return

            await self._send_transaction(all_ixs, market_index, order_uuid_str)

        except KeyError as e:
            print(f"Missing expected key in order message ({order_uuid_str}): {e}")
        except Exception as e:
            print(f"Error handling order {order_uuid_str}: {e}")

    async def _send_transaction(
        self, ixs: List[Instruction], market_index: int, order_uuid: str
    ):
        """Sends the transaction with the provided instructions after simulating."""
        start_time = time.time()
        print(f"Simulating transaction for order {order_uuid}...")

        send_start_time = time.time()
        print(f"Sending transaction for order {order_uuid}...")
        try:
            result = await self.drift_client.send_ixs(ixs)

            send_elapsed = time.time() - send_start_time
            total_elapsed = time.time() - start_time
            print(
                f"Transaction sent for order {order_uuid}. Signature: {result.tx_sig}, Slot: {result.slot}, Send Time: {send_elapsed:.3f}s, Total Time: {total_elapsed:.3f}s"
            )

        except Exception as e:
            print(f"Transaction Error: {e}")
            if hasattr(e, "logs") and e.logs:
                print(f"Transaction Error Logs: {e.logs}")
            if hasattr(e, "message"):
                print(f"  Error Message: {e.message}")
            if hasattr(e, "logs") and e.logs:
                print(f"  Logs: \n{''.join(e.logs)}")


async def main():
    load_dotenv()

    ENV = "mainnet"
    RPC_URL = os.getenv("RPC_TRITON")
    MAKER_PRIVATE_KEY = os.getenv("PRIVATE_KEY")
    WS_AUTH_PRIVATE_KEY = MAKER_PRIVATE_KEY
    DRY_RUN = "true"
    MARKETS = ["SOL-PERP", "BTC-PERP", "ETH-PERP"]

    if not RPC_URL or not MAKER_PRIVATE_KEY:
        raise ValueError("RPC_TRITON and PRIVATE_KEY must be set in .env")

    maker_keypair = load_keypair(MAKER_PRIVATE_KEY)
    auth_keypair = load_keypair(WS_AUTH_PRIVATE_KEY)

    print(f"Maker Pubkey: {maker_keypair.pubkey()}")
    print(f"WS Auth Pubkey: {auth_keypair.pubkey()}")
    print(f"RPC Endpoint: {RPC_URL}")
    print(f"Dry Run: {DRY_RUN}")
    print(f"Environment: {ENV}")

    connection = AsyncClient(RPC_URL, commitment=Commitment("confirmed"))
    wallet = Wallet(maker_keypair)

    drift_client = DriftClient(
        connection,
        wallet,
        env=ENV,
        # opts=TxOpts(skip_preflight=True),
    )
    print("Subscribing DriftClient...")
    await drift_client.subscribe()
    print("DriftClient subscribed.")

    user_map = UserMap(UserMapConfig(drift_client, PollingConfig(frequency=5)))
    print("Subscribing UserMap...")
    await user_map.subscribe()
    print("UserMap subscribed.")

    runtime_spec = RuntimeSpec(drift_env=ENV)

    swift_maker = SwiftMaker(
        drift_client=drift_client,
        user_map=user_map,
        runtime_spec=runtime_spec,
        auth_keypair=auth_keypair,
        markets_to_subscribe=MARKETS,
        dry_run=False,
    )

    await swift_maker.init()

    print("SwiftMaker initialized. Running indefinitely...")
    while True:
        await asyncio.sleep(60)
        if not swift_maker.is_connected or not swift_maker.is_authenticated:
            print("SwiftMaker appears disconnected/unauthenticated.")
        if not user_map.is_subscribed:
            print("UserMap appears unsubscribed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Received KeyboardInterrupt, shutting down...")
    except Exception as e:
        print(f"Unhandled exception in main: {e}")
        raise e
    finally:
        print("Shutdown complete.")
