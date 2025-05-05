import asyncio
import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import construct
import nacl.signing
from anchorpy import Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solana.rpc.types import TxOpts
from solders.instruction import Instruction
from solders.keypair import Keypair
from solders.message import MessageV0
from solders.pubkey import Pubkey
from solders.transaction import (
    VersionedTransaction,
)
from websockets.client import WebSocketClientProtocol, connect
from websockets.exceptions import ConnectionClosed, WebSocketException

from driftpy.accounts import get_user_stats_account_public_key
from driftpy.addresses import get_user_account_public_key
from driftpy.drift_client import DriftClient
from driftpy.keypair import load_keypair
from driftpy.swift.order_subscriber import SIGNED_MSG_DELEGATE_DISCRIMINATOR
from driftpy.types import (
    MarketType,
    OrderParams,
    OrderTriggerCondition,
    OrderType,
    PositionDirection,
    PostOnlyParams,
    is_variant,
)
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import PollingConfig, UserMapConfig

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


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
        markets_to_subscribe: List[str] = [
            "SOL-PERP",
            "BTC-PERP",
            "ETH-PERP",
        ],
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

        # TODO: Implement dynamic priority fee fetching if needed
        # self.priority_fee_subscriber = PriorityFeeSubscriberMap(...)

    def _get_ws_endpoint(self) -> str:
        if self.runtime_spec.drift_env == "mainnet":
            return "wss://swift.drift.trade/ws"
        elif self.runtime_spec.drift_env == "devnet":
            return "wss://master.swift.drift.trade/ws"
        else:
            raise ValueError(f"Unsupported drift_env: {self.runtime_spec.drift_env}")

    async def init(self):
        logger.info("Initializing SwiftMaker...")
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
                    logger.warning(
                        f"Heartbeat timeout ({self.heartbeat_timeout_s}s). Last received: {self.last_heartbeat_ts:.2f}. Reconnecting..."
                    )
                    asyncio.create_task(self._reconnect())
                    break  # Exit monitor task on timeout/reconnect attempt

        logger.info("Starting heartbeat monitor task.")
        self.last_heartbeat_ts = time.time()  # Reset timestamp on start
        self.heartbeat_task = asyncio.create_task(_heartbeat_monitor())

    async def _reconnect(self):
        logger.info("Attempting to reconnect...")
        self.is_connected = False
        self.is_authenticated = False
        if self.ws:
            try:
                await self.ws.close()
            except WebSocketException as e:
                logger.error(f"Error closing websocket during reconnect: {e}")
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
        logger.info(f"Connecting to WebSocket: {connect_url}")

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
                logger.info("WebSocket connection established.")
                self._start_heartbeat_check()

                async for raw_message in websocket:
                    self.last_heartbeat_ts = time.time()

                    try:
                        message = json.loads(raw_message)
                        await self._process_message(message)
                    except json.JSONDecodeError:
                        logger.warning(f"Received non-JSON message: {raw_message}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}", exc_info=True)

        except (
            ConnectionClosed,
            WebSocketException,
            asyncio.TimeoutError,
            OSError,
        ) as e:
            logger.error(f"WebSocket connection error: {e}. Attempting reconnect...")
            self.is_connected = False
            self.is_authenticated = False
            await self._reconnect()
        except Exception as e:
            logger.error(f"Unexpected error in subscribe_ws: {e}", exc_info=True)
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
                logger.info("WebSocket successfully authenticated.")
                self.is_authenticated = True
                await self._subscribe_to_markets()
            elif isinstance(msg_type, str):
                logger.warning(f"Received auth message: {msg_type}")

        elif "order" in message and self.is_authenticated:
            if self.user_map.is_subscribed:
                asyncio.create_task(self._handle_order(message["order"]))
            else:
                logger.warning(
                    "Received order message but DriftClient/UserMap not ready. Skipping."
                )

        elif channel == "heartbeat":
            # logger.debug("Received heartbeat message.") # Can be noisy
            pass  # Handled by last_heartbeat_ts update

        else:
            logger.debug(f"Received unhandled message: {message}")

    async def _handle_auth_challenge(self, nonce: str):
        """Signs the auth nonce and sends it back."""
        if not self.ws:
            logger.error("Cannot handle auth challenge, WebSocket is not connected.")
            return

        logger.info("Received auth challenge, signing nonce...")
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
            logger.info("Sent authentication response.")
        except WebSocketException as e:
            logger.error(f"Failed to send authentication response: {e}")
            # Consider triggering reconnect here

    async def _subscribe_to_markets(self):
        """Sends subscription requests for the configured markets."""
        if not self.ws or not self.is_authenticated:
            logger.error(
                "Cannot subscribe to markets, WebSocket not connected or authenticated."
            )
            return

        logger.info(f"Subscribing to markets: {self.markets_to_subscribe}")
        for market_name in self.markets_to_subscribe:
            sub_payload = {
                "action": "subscribe",
                "market_type": "perp",  # Assuming perp markets for now
                "market_name": market_name,
            }
            try:
                await self.ws.send(json.dumps(sub_payload))
                logger.debug(f"Sent subscription request for {market_name}")
                await asyncio.sleep(0.1)  # Slight delay between subscriptions
            except WebSocketException as e:
                logger.error(f"Failed to send subscription for {market_name}: {e}")
                # Consider triggering reconnect or retrying

    async def _handle_order(self, order_message_raw: Dict):
        """Processes a received order, generates maker instructions, and potentially sends the transaction."""
        order_received_ts = time.time()
        order_uuid_str = order_message_raw.get("uuid", "unknown_uuid")
        logger.info(
            f"Handling order {order_uuid_str} received at {order_received_ts:.3f}"
        )

        try:
            # 1. Decode and Validate Order
            signed_msg_order_params_buf_hex = order_message_raw["order_message"]
            signed_msg_order_params_buf = bytes.fromhex(signed_msg_order_params_buf_hex)
            taker_signature = base64.b64decode(order_message_raw["order_signature"])
            order_uuid = order_uuid_str.encode("utf-8")

            discriminator = signed_msg_order_params_buf[:8]
            is_delegate = discriminator == SIGNED_MSG_DELEGATE_DISCRIMINATOR

            try:
                signed_message = (
                    self.drift_client.decode_signed_msg_order_params_message(
                        signed_msg_order_params_buf, is_delegate=is_delegate
                    )
                )
            except construct.core.StreamError as e:
                logger.error(f"Failed to decode order message ({order_uuid_str}): {e}")
                logger.error(
                    f"  Buffer (len={len(signed_msg_order_params_buf)}): {signed_msg_order_params_buf.hex()}"
                )
                return

            taker_order_params = signed_message.signed_msg_order_params
            market_index = taker_order_params.market_index

            if (
                not taker_order_params.price
                and taker_order_params.auction_duration == 0
            ):
                logger.warning(
                    f"Order {order_uuid_str} has no price/auction params. Skipping."
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
                logger.error(
                    f"Could not find taker user account in UserMap: {taker_user_pubkey}"
                )
                return
            taker_user_account = taker_user_map_entry.get_user_account()
            taker_stats_pubkey = get_user_stats_account_public_key(
                self.drift_client.program.program_id, taker_user_account.authority
            )

            is_taker_long = is_variant(taker_order_params.direction, "Long")
            maker_direction = (
                PositionDirection.Short() if is_taker_long else PositionDirection.Long()
            )

            maker_base_amount = taker_order_params.base_asset_amount // 2
            if maker_base_amount == 0:
                logger.warning(
                    f"Maker base amount is zero for order {order_uuid_str}. Skipping."
                )
                return

            if taker_order_params.auction_duration > 0:
                maker_price = (
                    int(taker_order_params.auction_start_price * 0.99)
                    if is_taker_long
                    else int(taker_order_params.auction_end_price * 1.01)
                )
                logger.info(
                    f"Order {order_uuid_str}: Auction fill at price {maker_price}"
                )
            elif taker_order_params.price > 0:
                maker_price = taker_order_params.price
                logger.info(
                    f"Order {order_uuid_str}: Limit fill at price {maker_price}"
                )
            else:
                logger.warning(
                    f"Order {order_uuid_str}: Cannot determine maker price. Skipping."
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
                user_order_id=0,
                reduce_only=False,
                trigger_price=0,
                trigger_condition=OrderTriggerCondition.Above(),
                auction_start_price=0,
                auction_end_price=0,
                auction_duration=0,
                max_ts=None,
                oracle_price_offset=None,
            )

            taker_info = {
                "taker": taker_user_pubkey,
                "taker_user_account": taker_user_account,
                "taker_stats": taker_stats_pubkey,
                "signing_authority": signing_authority,
            }

            preceding_ixs = []

            logger.info(f"Constructing place_and_make IXs for order {order_uuid_str}")
            fill_ixs = (
                await self.drift_client.get_place_and_make_signed_msg_perp_order_ixs(
                    signed_msg_order_params={
                        "order_params": signed_msg_order_params_buf,
                        "signature": taker_signature,
                    },
                    signed_msg_order_uuid=order_uuid,
                    taker_info=taker_info,
                    order_params=maker_order_params,
                    preceding_ixs=preceding_ixs,  # Pass empty list here
                )
            )

            all_ixs = preceding_ixs + fill_ixs
            logger.info(
                f"Generated {len(fill_ixs)} fill instructions for order {order_uuid_str}."
            )

            if self.dry_run:
                processing_time = time.time() - order_received_ts
                logger.info(
                    f"[Dry Run] Would fill order {order_uuid_str}. Processing time: {processing_time:.3f}s"
                )
                logger.info(f"[Dry Run]  Taker: {taker_user_pubkey}")
                logger.info(
                    f"[Dry Run]  Maker Direction: {maker_direction}, Base: {maker_base_amount}, Price: {maker_price}"
                )
                logger.info(f"[Dry Run]  Instructions ({len(all_ixs)}):")
                for i, ix in enumerate(all_ixs):
                    print(ix)
                return

            await self._send_transaction(all_ixs, market_index, order_uuid_str)

        except KeyError as e:
            logger.error(
                f"Missing expected key in order message ({order_uuid_str}): {e}"
            )
        except Exception as e:
            logger.error(f"Error handling order {order_uuid_str}: {e}", exc_info=True)

    async def _send_transaction(
        self, ixs: List[Instruction], market_index: int, order_uuid: str
    ):
        """Sends the transaction with the provided instructions after simulating."""
        start_time = time.time()
        logger.info(f"Simulating transaction for order {order_uuid}...")

        # --- Simulate Transaction ---
        # try:
        #     # --- Prepare Versioned Transaction for Simulation ---
        #     latest_blockhash_data = (
        #         await self.drift_client.connection.get_latest_blockhash()
        #     )
        #     latest_blockhash = latest_blockhash_data.value.blockhash

        #     # Lookup tables (fetch if needed, assuming DriftClient might cache them or provide a way)
        #     # For now, assume send_ixs handles this, and use empty for simulation if needed
        #     # lookup_tables = await self.drift_client.fetch_market_lookup_table_accounts() # Potentially needed
        #     lookup_tables = []

        #     msg = MessageV0.try_compile(
        #         payer=self.drift_client.wallet.payer.pubkey(),
        #         instructions=ixs,
        #         address_lookup_table_accounts=lookup_tables,
        #         recent_blockhash=latest_blockhash,
        #     )

        #     # Signers: the maker's keypair
        #     signers = [self.drift_client.wallet.payer]

        #     tx = VersionedTransaction(msg, signers)

        #     simulation_result = await self.drift_client.connection.simulate_transaction(
        #         tx,
        #         commitment=Commitment("confirmed"),  # Use commitment for simulation
        #     )

        #     sim_elapsed = time.time() - start_time
        #     if simulation_result.value.err:
        #         logger.error(
        #             f"Transaction simulation failed for order {order_uuid} after {sim_elapsed:.3f}s:"
        #         )
        #         err_info = simulation_result.value.err
        #         logger.error(f"  Raw Error: {err_info}")

        #         # --- Decode Error using IDL ---
        #         ix_err = err_info.err.value
        #         print(ix_err)

        #         error_code = ix_err
        #         try:
        #             idl_errors = self.drift_client.program.idl.errors
        #             found_error = None
        #             for e in idl_errors:
        #                 if e.code == error_code:
        #                     found_error = e
        #                     break
        #             if found_error:
        #                 logger.error(
        #                     f"  Decoded Error (Ix {ix_index}): {found_error.name} ({found_error.code}) - {found_error.msg}"
        #                 )
        #             else:
        #                 logger.error(
        #                     f"  Error code {error_code} not found in Drift IDL errors."
        #                 )
        #         except Exception as e:
        #             print(e)
        #         else:
        #             logger.error(f"  Instruction Error Type: {type(ix_err)}")
        #         # --- End Decode Error ---

        #         if simulation_result.value.logs:
        #             logger.error("  Logs:")
        #             for log in simulation_result.value.logs:
        #                 logger.error(f"    {log}")
        #         return  # Stop here if simulation fails
        #     else:
        #         logger.info(
        #             f"Transaction simulation successful for order {order_uuid} (took {sim_elapsed:.3f}s)."
        #         )
        #         logger.info(
        #             f"  Compute Units Used: {simulation_result.value.units_consumed}"
        #         )
        #         if simulation_result.value.logs:
        #             logger.info("  Simulation Logs:")
        #             for log in simulation_result.value.logs:
        #                 logger.info(f"    {log}")

        # except Exception as e:
        #     sim_elapsed = time.time() - start_time
        #     logger.error(
        #         f"Error during transaction simulation for order {order_uuid} after {sim_elapsed:.3f}s: {e}",
        #         exc_info=True,
        #     )
        #     return  # Stop if simulation itself errors

        # --- Send Transaction (if simulation was successful) ---
        send_start_time = time.time()
        logger.info(f"Sending transaction for order {order_uuid}...")
        try:
            # Send using the existing send_ixs method which handles blockhash and lookup tables
            result = await self.drift_client.send_ixs(ixs)

            send_elapsed = time.time() - send_start_time
            total_elapsed = time.time() - start_time
            logger.info(
                f"Transaction sent for order {order_uuid}. Signature: {result.tx_sig}, Slot: {result.slot}, Send Time: {send_elapsed:.3f}s, Total Time: {total_elapsed:.3f}s"
            )

        except Exception as e:
            logger.error(f"Transaction Error: {e}")
            if hasattr(e, "logs") and e.logs:
                logger.error(f"Transaction Error Logs: {e.logs}")
            # Log more details if available
            if hasattr(e, "message"):
                logger.error(f"  Error Message: {e.message}")
            if hasattr(e, "logs") and e.logs:
                logger.error(f"  Logs: \n{''.join(e.logs)}")

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"Failed to send transaction for order {order_uuid} after {elapsed:.3f}s: {e}",
                exc_info=True,
            )
            logger.error(f"  Logs: {e}")


async def main():
    load_dotenv()

    ENV = "mainnet"
    RPC_URL = os.getenv("RPC_TRITON")
    MAKER_PRIVATE_KEY = os.getenv("PRIVATE_KEY")
    WS_AUTH_PRIVATE_KEY = MAKER_PRIVATE_KEY
    DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
    MARKETS = ["SOL-PERP", "BTC-PERP", "ETH-PERP"]  # Markets to MM

    if not RPC_URL or not MAKER_PRIVATE_KEY:
        raise ValueError("RPC_TRITON and PRIVATE_KEY must be set in .env")

    maker_keypair = load_keypair(MAKER_PRIVATE_KEY)
    auth_keypair = load_keypair(WS_AUTH_PRIVATE_KEY)

    logger.info(f"Maker Pubkey: {maker_keypair.pubkey()}")
    logger.info(f"WS Auth Pubkey: {auth_keypair.pubkey()}")
    logger.info(f"RPC Endpoint: {RPC_URL}")
    logger.info(f"Dry Run: {DRY_RUN}")
    logger.info(f"Environment: {ENV}")

    connection = AsyncClient(RPC_URL, commitment=Commitment("confirmed"))
    wallet = Wallet(maker_keypair)

    drift_client = DriftClient(
        connection, wallet, env=ENV, opts=TxOpts(skip_preflight=True)
    )
    logger.info("Subscribing DriftClient...")
    await drift_client.subscribe()
    logger.info("DriftClient subscribed.")

    user_map = UserMap(UserMapConfig(drift_client, PollingConfig(frequency=5)))
    logger.info("Subscribing UserMap...")
    await user_map.subscribe()
    logger.info("UserMap subscribed.")

    runtime_spec = RuntimeSpec(drift_env=ENV)

    swift_maker = SwiftMaker(
        drift_client=drift_client,
        user_map=user_map,
        runtime_spec=runtime_spec,
        auth_keypair=auth_keypair,
        markets_to_subscribe=MARKETS,
    )

    await swift_maker.init()

    logger.info("SwiftMaker initialized. Running indefinitely...")
    while True:
        await asyncio.sleep(60)
        if not swift_maker.is_connected or not swift_maker.is_authenticated:
            logger.warning("SwiftMaker appears disconnected/unauthenticated.")
        if not user_map.is_subscribed:
            logger.warning("UserMap appears unsubscribed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down...")
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {e}", exc_info=True)
    finally:
        logger.info("Shutdown complete.")
