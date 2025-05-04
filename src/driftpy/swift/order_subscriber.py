import asyncio
import base64
import json
import logging
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Callable, Dict, List, Optional

import construct
import nacl.signing
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from websockets.client import WebSocketClientProtocol, connect
from websockets.exceptions import ConnectionClosed

from driftpy.accounts import get_user_stats_account_public_key
from driftpy.addresses import get_user_account_public_key
from driftpy.constants.perp_markets import (
    devnet_perp_market_configs,
    mainnet_perp_market_configs,
)
from driftpy.drift_client import DriftClient
from driftpy.types import MarketType, PostOnlyParams, SignedMsgOrderParamsMessage
from driftpy.user_map.user_map import UserMap

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SIGNED_MSG_STANDARD_DISCRIMINATOR = sha256(
    b"global:SignedMsgOrderParamsMessage"
).digest()[:8]
SIGNED_MSG_DELEGATE_DISCRIMINATOR = sha256(
    b"global:SignedMsgOrderParamsDelegateMessage"
).digest()[:8]


@dataclass
class SwiftOrderSubscriberConfig:
    drift_client: DriftClient
    keypair: Keypair  # Required for authentication
    user_map: Optional[UserMap] = None
    drift_env: str = "mainnet-beta"
    endpoint: Optional[str] = None
    market_indexes: List[int] = field(default_factory=list)


class SwiftOrderSubscriber:
    def __init__(self, config: SwiftOrderSubscriberConfig):
        self.config = config
        self.drift_client = config.drift_client
        self.user_map = config.user_map
        self.ws: Optional[WebSocketClientProtocol] = None
        self.heartbeat_task = None
        self.heartbeat_interval = 60
        self.subscribed = False
        self.on_order = None

    def get_symbol_for_market_index(self, market_index: int) -> str:
        markets = (
            devnet_perp_market_configs
            if self.config.drift_env == "devnet"
            else mainnet_perp_market_configs
        )
        symbol = markets[market_index].symbol
        return symbol

    def generate_challenge_response(self, nonce: str) -> str:
        message_bytes = nonce.encode("utf-8")
        signing_key = nacl.signing.SigningKey(self.config.keypair.secret())
        signature = signing_key.sign(message_bytes).signature
        response = base64.b64encode(signature).decode("utf-8")
        return response

    async def handle_auth_message(self, message: Dict) -> None:
        if self.ws is None:
            logger.warning("WebSocket connection not established")
            return

        if message.get("channel") == "auth" and message.get("nonce"):
            signature_base64 = self.generate_challenge_response(message["nonce"])
            await self.ws.send(
                json.dumps(
                    {
                        "pubkey": str(self.config.keypair.pubkey()),
                        "signature": signature_base64,
                    }
                )
            )

        if (
            message.get("channel") == "auth"
            and isinstance(message.get("message"), str)
            and message["message"].lower() == "authenticated"
        ):
            print("Successfully authenticated")
            self.subscribed = True
            for market_index in self.config.market_indexes:
                print(f"Subscribing to market index: {market_index}")
                await self.ws.send(
                    json.dumps(
                        {
                            "action": "subscribe",
                            "market_type": "perp",
                            "market_name": self.get_symbol_for_market_index(
                                market_index
                            ),
                        }
                    )
                )
                await asyncio.sleep(0.1)

    async def subscribe(
        self, on_order: Callable[[Dict, SignedMsgOrderParamsMessage], None]
    ) -> None:
        print("Starting subscription process")
        self.on_order = on_order
        endpoint = "wss://swift.drift.trade/ws"

        if self.config.endpoint:
            endpoint = self.config.endpoint
        if self.config.drift_env == "devnet":
            endpoint = "wss://master.swift.drift.trade/ws"

        while True:
            try:
                async with connect(
                    f"{endpoint}?pubkey={str(self.config.keypair.pubkey())}",
                    open_timeout=60,
                    ping_interval=20,
                    ping_timeout=60,
                ) as websocket:
                    self.ws = websocket
                    print(f"Connected to {endpoint} server")

                    while True:
                        try:
                            raw_message = await websocket.recv()
                            message = json.loads(raw_message)

                            if message.get("channel") == "auth":
                                await self.handle_auth_message(message)

                            if message.get("order"):
                                order = message["order"]
                                signed_order_params_buf = bytes.fromhex(
                                    order["order_message"]
                                )

                                discriminator = signed_order_params_buf[:8]
                                decoded_message = None
                                message_type = None

                                if discriminator == SIGNED_MSG_DELEGATE_DISCRIMINATOR:
                                    message_type = "SignedMsgOrderParamsDelegateMessage"
                                    try:
                                        decoded_message = self.drift_client.decode_signed_msg_order_params_message(
                                            signed_order_params_buf, is_delegate=True
                                        )
                                    except construct.core.StreamError as e:
                                        logger.error(
                                            f"Failed to decode {message_type}: {e}"
                                        )
                                        logger.error(
                                            f"  Buffer (len={len(signed_order_params_buf)}): {signed_order_params_buf.hex()}"
                                        )
                                        continue
                                elif discriminator == SIGNED_MSG_STANDARD_DISCRIMINATOR:
                                    message_type = "SignedMsgOrderParamsMessage"
                                    try:
                                        decoded_message = self.drift_client.decode_signed_msg_order_params_message(
                                            signed_order_params_buf, is_delegate=False
                                        )
                                    except construct.core.StreamError as e:
                                        logger.error(
                                            f"Failed to decode {message_type}: {e}"
                                        )
                                        logger.error(
                                            f"  Buffer (len={len(signed_order_params_buf)}): {signed_order_params_buf.hex()}"
                                        )
                                        continue
                                else:
                                    logger.warning(
                                        f"Received unknown message type with discriminator: {discriminator.hex()}"
                                    )
                                    continue

                                if decoded_message is None:
                                    logger.error(
                                        "Decoding failed unexpectedly after checks."
                                    )
                                    continue
                                asyncio.create_task(on_order(order, decoded_message))

                        except ConnectionClosed:
                            logger.error("WebSocket connection closed")
                            break

            except asyncio.TimeoutError:
                logger.error("Connection timed out, waiting before retry...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"WebSocket error: {e}", exc_info=True)
                await asyncio.sleep(5)

            print("Disconnected from server, reconnecting...")
            await asyncio.sleep(1)

    async def unsubscribe(self):
        self.subscribed = False
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                logger.info("Heartbeat task cancelled.")
            self.heartbeat_task = None
        if self.ws:
            await self.ws.close()
            self.ws = None
            logger.info("WebSocket connection closed.")

    async def get_place_and_make_signed_msg_order_ixs(
        self,
        order_message_raw: Dict,
        signed_msg_order_params_message: SignedMsgOrderParamsMessage,
        maker_order_params: Dict,
    ):
        signed_msg_order_params_buf = bytes.fromhex(order_message_raw["order_message"])
        taker_authority = Pubkey.from_string(order_message_raw["taker_authority"])
        taker_user_pubkey = get_user_account_public_key(
            self.drift_client.program_id,
            taker_authority,
            signed_msg_order_params_message.sub_account_id,
        )

        taker_user_account = (
            await self.user_map.must_get(str(taker_user_pubkey))
        ).get_user_account()

        maker_order_params.update(
            {
                "post_only": PostOnlyParams.MustPostOnly,
                "immediate_or_cancel": True,
                "market_type": MarketType.Perp,
            }
        )

        ixs = await self.drift_client.get_place_and_make_signed_msg_perp_order_ixs(
            {
                "order_params": signed_msg_order_params_buf,
                "signature": base64.b64decode(order_message_raw["order_signature"]),
                "user_stats": get_user_stats_account_public_key(
                    self.drift_client.program_id, taker_user_account.authority
                ),
            },
            order_message_raw["uuid"].encode("utf-8"),
            {
                "taker": taker_user_pubkey,
                "taker_user_account": taker_user_account,
                "taker_stats": get_user_stats_account_public_key(
                    self.drift_client.program_id, taker_user_account.authority
                ),
            },
            maker_order_params,
        )
        return ixs
