import asyncio
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solana.rpc.websocket_api import SolanaWsClientProtocol
from solders.pubkey import Pubkey
from solders.rpc.config import RpcTransactionLogsFilterMentions

from solana.rpc.websocket_api import connect

from typing import cast

import websockets.exceptions

from driftpy.events.types import LogProviderCallback, LogProvider


class WebsocketLogProvider(LogProvider):
    def __init__(
        self, connection: AsyncClient, address: Pubkey, commitment: Commitment
    ):
        self.connection = connection
        self.address = address
        self.commitment = commitment
        self.task = None

    def subscribe(self, callback: LogProviderCallback):
        if not self.is_subscribed():
            self.task = asyncio.create_task(self.subscribe_ws(callback))

    async def subscribe_ws(self, callback: LogProviderCallback):
        endpoint = self.connection._provider.endpoint_uri
        ws_endpoint = endpoint.replace("https", "wss").replace("http", "ws")
        async for ws in connect(ws_endpoint):
            ws: SolanaWsClientProtocol
            try:
                await ws.logs_subscribe(
                    RpcTransactionLogsFilterMentions(self.address),
                    self.commitment,
                )

                first_resp = await ws.recv()
                subscription_id = cast(int, first_resp[0].result)

                async for msg in ws:
                    try:
                        slot = msg[0].result.context.slot
                        signature = msg[0].result.value.signature
                        logs = msg[0].result.value.logs

                        if msg[0].result.value.err:
                            continue

                        callback(signature, slot, logs)
                    except Exception as e:
                        print("Error processing event data", e)
                        break
                await ws.account_unsubscribe(subscription_id)
            except websockets.exceptions.ConnectionClosed:
                print("Websocket closed, reconnecting...")
                continue

    def is_subscribed(self) -> bool:
        return self.task is not None

    def unsubscribe(self):
        if self.is_subscribed():
            self.task.cancel()
            self.task = None
