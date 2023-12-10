import asyncio
from typing import Dict, Optional, TypeVar, Callable
from anchorpy import Program
from driftpy.accounts.types import DataAndSlot, UpdateCallback, WebsocketOptions
from solana.rpc.websocket_api import connect, SolanaWsClientProtocol
from solders.pubkey import Pubkey


T = TypeVar("T")

class WebSocketMultiAccountSubscriber:
    def __init__(
            self,
            program: Program,
            options: WebsocketOptions,
            on_update: UpdateCallback,
            decode: Optional[Callable[[bytes], T]] = None,
        ):
        self.program = program
        self.options = options
        self.task = None
        self.on_update = on_update
        self.decode = (
            decode if decode is not None else self.program.coder.accounts.decode
        )
        self.subscribed_accounts: Dict[Pubkey, DataAndSlot[T]] = {}
        
    async def subscribe(self): 
        self.task = asyncio.create_task(self.subscribe_ws())
        return self.task

    async def subscribe_ws(self):
        endpoint = self.program.provider.connection._provider.endpoint_uri
        ws_endpoint = endpoint.replace("https", "wss").replace("http", "ws")
        async with connect(ws_endpoint) as ws:
            self.ws = ws
            ws: SolanaWsClientProtocol
            try:
                await ws.program_subscribe(
                    self.program.program_id,
                    self.options.commitment,
                    self.options.encoding,
                    filters = self.options.filters
                )
                # Start streaming account data to be processed 
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

            except Exception as e:
                print(f"Connection failed: {e}")

    def _update_data(self, account: Pubkey, new_data: Optional[DataAndSlot[T]]):
        if new_data is None:
            return
        self.subscribed_accounts[account] = new_data

    def unsubscribe(self):
        if self.task:
            self.task.cancel()
            self.task = None
        if self.ws:
            self.ws.close()
            self.ws = None

            