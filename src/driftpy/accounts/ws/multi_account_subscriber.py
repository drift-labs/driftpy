import asyncio
from typing import Optional, TypeVar, Callable
from anchorpy import Program
from driftpy.accounts.types import DataAndSlot, WebsocketOptions
from solana.rpc.websocket_api import connect, SolanaWsClientProtocol
from solders.pubkey import Pubkey

T = TypeVar("T")

class WebSocketMultiAccountSubscriber:
    def __init__(
            self,
            program: Program,
            options: WebsocketOptions,
            on_update,
            decode: Optional[Callable[[bytes], T]] = None,
        ):
        self.program = program
        self.commitment = options.commitment
        self.options = options
        self.task = None
        self.on_update = on_update
        self.decode = (
            decode if decode is not None else self.program.coder.accounts.decode
        )
        self.subscribed_accounts = {}
        
    async def subscribe(self): 
        self.task = asyncio.create_task(self.subscribe_ws())
        return self.task

    async def subscribe_ws(self):
        endpoint = self.program.provider.connection._provider.endpoint_uri
        ws_endpoint = endpoint.replace("https", "wss").replace("http", "ws")
        print(ws_endpoint)
        async with connect(ws_endpoint) as ws:
            ws: SolanaWsClientProtocol
            try:
                await ws.program_subscribe(
                    self.program.program_id,
                    self.commitment,
                    "base64",
                    filters = self.options.filters
                )
                await ws.recv()

                async for msg in ws:
                    try:
                        for item in msg:
                            res = item.result
                            slot = res.context.slot
                            data = self.decode(res.value.account.data)
                            new_data = DataAndSlot(slot, data)
                            pubkey = res.value.pubkey
                            await self.on_update(str(pubkey), new_data)
                    except Exception as e:
                        print(f"Error processing acount data: {e}")
                        break

            except Exception as e:
                print(f"Connection failed: {e}")

    def _update_data(self, account: Pubkey, new_data: Optional[DataAndSlot[T]]):
        if new_data is None:
            return
        self.subscribed_accounts[account] = new_data

    def unsubscribe(self):
        self.task.cancel()
        self.task = None

            