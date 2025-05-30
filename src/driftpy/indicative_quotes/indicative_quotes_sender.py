import asyncio
import base64
import json
import logging
from typing import Dict, Optional

import nacl.signing
import websockets
from solders.keypair import Keypair
from websockets.exceptions import ConnectionClosed, WebSocketException

SEND_INTERVAL = 0.5  # 500ms in seconds


class Quote:
    def __init__(
        self,
        bid_price: int,
        ask_price: int,
        bid_base_asset_amount: int,
        ask_base_asset_amount: int,
        market_index: int,
        is_oracle_offset: Optional[bool] = None,
    ):
        self.bid_price = bid_price
        self.ask_price = ask_price
        self.bid_base_asset_amount = bid_base_asset_amount
        self.ask_base_asset_amount = ask_base_asset_amount
        self.market_index = market_index
        self.is_oracle_offset = is_oracle_offset


class IndicativeQuotesSender:
    def __init__(self, endpoint: str, keypair: Keypair):
        self.endpoint = endpoint
        self.keypair = keypair

        self.heartbeat_interval_ms = 60000  # 60 seconds
        self.reconnect_delay = 1.0  # 1 second

        self.ws = None
        self.connected = False
        self.quotes: Dict[int, Quote] = {}

        self.heartbeat_task = None
        self.send_quotes_task = None
        self.reconnect_task = None

        self.logger = logging.getLogger(__name__)

    def generate_challenge_response(self, nonce: str) -> str:
        """Generate signature for authentication challenge"""
        message_bytes = nonce.encode("utf-8")
        signing_key = nacl.signing.SigningKey(self.keypair.secret()[:32])
        signature = signing_key.sign(message_bytes).signature
        return base64.b64encode(signature).decode("utf-8")

    async def handle_auth_message(self, message: dict):
        """Handle authentication messages from server"""
        if message.get("channel") == "auth" and message.get("nonce"):
            signature_base64 = self.generate_challenge_response(message["nonce"])
            auth_response = {
                "pubkey": str(self.keypair.pubkey()),
                "signature": signature_base64,
            }
            await self.ws.send(json.dumps(auth_response))

        if (
            message.get("channel") == "auth"
            and message.get("message", "").lower() == "authenticated"
        ):
            self.connected = True
            self.logger.info("Successfully authenticated")

            # Start sending quotes after authentication
            if self.send_quotes_task:
                self.send_quotes_task.cancel()
            self.send_quotes_task = asyncio.create_task(self._send_quotes_loop())

    async def _send_quotes_loop(self):
        """Send quotes at regular intervals"""
        while self.connected:
            try:
                for market_index, quote in self.quotes.items():
                    message = {
                        "market_type": "perp",
                        "market_index": market_index,
                        "bid_price": str(quote.bid_price),
                        "ask_price": str(quote.ask_price),
                        "bid_size": str(quote.bid_base_asset_amount),
                        "ask_size": str(quote.ask_base_asset_amount),
                        "is_oracle_offset": quote.is_oracle_offset,
                    }

                    if self.ws and not self.ws.closed:
                        await self.ws.send(json.dumps(message))

                await asyncio.sleep(SEND_INTERVAL)
            except Exception as e:
                self.logger.error(f"Error sending quote: {e}")
                break

    async def _heartbeat_timer(self):
        """Monitor heartbeat and reconnect if needed"""
        await asyncio.sleep(self.heartbeat_interval_ms / 1000)
        self.logger.warning("No heartbeat received within 60 seconds, reconnecting...")
        await self._reconnect()

    async def connect(self):
        """Connect to WebSocket server"""
        uri = f"{self.endpoint}?pubkey={str(self.keypair.pubkey())}"

        try:
            self.ws = await websockets.connect(uri)
            self.logger.info("Connected to the server")
            self.reconnect_delay = 1.0

            # Start heartbeat timer
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
            self.heartbeat_task = asyncio.create_task(self._heartbeat_timer())

            async for message in self.ws:
                try:
                    data = json.loads(message)

                    # Reset heartbeat timer on any message
                    if self.heartbeat_task:
                        self.heartbeat_task.cancel()
                    self.heartbeat_task = asyncio.create_task(self._heartbeat_timer())

                    if data.get("channel") == "auth":
                        await self.handle_auth_message(data)

                except json.JSONDecodeError:
                    self.logger.warning(f"Failed to parse json message: {message}")
                except Exception as e:
                    self.logger.error(f"Error handling message: {e}")

        except (ConnectionClosed, WebSocketException) as e:
            self.logger.info(f"WebSocket connection closed: {e}")
            await self._reconnect()
        except Exception as e:
            self.logger.error(f"WebSocket error: {e}")
            await self._reconnect()

    async def _reconnect(self):
        """Reconnect to WebSocket with exponential backoff"""
        self.connected = False

        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.send_quotes_task:
            self.send_quotes_task.cancel()

        if self.ws:
            await self.ws.close()

        self.logger.info(
            f"Reconnecting to WebSocket in {self.reconnect_delay} seconds..."
        )
        await asyncio.sleep(self.reconnect_delay)

        self.reconnect_delay = min(self.reconnect_delay * 2, 30.0)

        await self.connect()

    def set_quote(self, quote: Quote):
        """Set or update a quote for a market"""
        if not self.connected:
            self.logger.warning(
                "Setting quote before connected to the server, ignoring"
            )
            return

        self.quotes[quote.market_index] = quote

    async def close(self):
        """Close connection and cleanup"""
        self.connected = False

        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.send_quotes_task:
            self.send_quotes_task.cancel()
        if self.reconnect_task:
            self.reconnect_task.cancel()

        if self.ws:
            await self.ws.close()
