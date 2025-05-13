import asyncio
from typing import cast

import websockets.exceptions
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solana.rpc.websocket_api import SolanaWsClientProtocol, connect
from solders.pubkey import Pubkey
from solders.rpc.config import RpcTransactionLogsFilterMentions

from driftpy.events.types import LogProvider, LogProviderCallback
from driftpy.types import get_ws_url


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
        if endpoint.startswith("http"):
            ws_endpoint = get_ws_url(endpoint)
        else:
            ws_endpoint = endpoint

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
