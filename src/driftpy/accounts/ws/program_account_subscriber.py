import asyncio
from typing import Callable, Dict, Optional, TypeVar

from anchorpy.program.core import Program
from solana.rpc.websocket_api import SolanaWsClientProtocol, connect
from solders.pubkey import Pubkey

from driftpy.accounts.types import (
    DataAndSlot,
    UpdateCallback,
    WebsocketProgramAccountOptions,
)
from driftpy.types import get_ws_url

T = TypeVar("T")


class WebSocketProgramAccountSubscriber:
    def __init__(
        self,
        subscription_name: str,
        program: Program,
        # options has the filters / commitment / encoding for `program_subscribe()`
        # think having them all in one type is cleaner
        options: WebsocketProgramAccountOptions,
        on_update: Optional[UpdateCallback],
        decode: Optional[Callable[[bytes], T]] = None,
        resub_timeout_ms: Optional[int] = None,
    ):
        self.subscription_name = subscription_name
        self.program = program
        self.options = options
        self.task = None
        self.on_update = on_update
        self.decode = (
            decode if decode is not None else self.program.coder.accounts.decode
        )
        self.subscribed_accounts: Dict[Pubkey, DataAndSlot[T]] = {}
        self.ws = None
        self.resub_timeout_ms = (
            resub_timeout_ms if resub_timeout_ms is not None else 1000
        )
        self.receiving_data = False
        self.subscribed = False
        self.is_unsubscribing = False
        self.latest_slot = 0

    async def subscribe(self):
        if self.subscribed:
            return
        self.task = asyncio.create_task(self.subscribe_ws())
        return self.task

    async def subscribe_ws(self):
        endpoint = self.program.provider.connection._provider.endpoint_uri
        ws_endpoint = get_ws_url(endpoint)
        while True:
            try:
                async with connect(ws_endpoint) as ws:
                    self.ws = ws
                    ws: SolanaWsClientProtocol

                    await ws.program_subscribe(
                        self.program.program_id,
                        self.options.commitment,
                        self.options.encoding,
                        filters=self.options.filters,
                    )

                    last_received_ts = asyncio.get_event_loop().time()
                    await ws.recv()

                    async for msg in ws:
                        await self._process_message(msg)

                        last_received_ts = asyncio.get_event_loop().time()
                        if (
                            asyncio.get_event_loop().time() - last_received_ts
                            > self.resub_timeout_ms / 1000
                        ):
                            if not self.receiving_data:
                                print(
                                    f"WebSocket timeout reached.  Resubscribing to {self.subscription_name}"
                                )
                                await self.ws.close()
                                self.ws = None
                                break
                            else:
                                self.receiving_data = False
            except Exception as e:
                print(f"Error in subscription {self.subscription_name}: {e}")
                if self.ws:
                    await self.ws.close()
                    self.ws = None
                await asyncio.sleep(5)  # wait a second before we retry

    async def _process_message(self, msg):
        for item in msg:
            res = item.result
            slot = res.context.slot
            if slot >= self.latest_slot:
                self.latest_slot = slot
                data = self.decode(res.value.account.data)
                new_data = DataAndSlot(slot, data)
                pubkey = res.value.pubkey
                if self.on_update is not None and callable(self.on_update):
                    await self.on_update(str(pubkey), new_data)
                self.receiving_data = True
            else:
                print(f"Received stale data from slot {slot}")

    def _update_data(self, account: Pubkey, new_data: Optional[DataAndSlot[T]]):
        if new_data is None:
            return
        self.subscribed_accounts[account] = new_data

    async def unsubscribe(self):
        self.is_unsubscribing = True
        self.receiving_data = False
        if self.task:
            self.task.cancel()
            self.task = None
        if self.ws:
            await self.ws.close()
            self.ws = None
        self.is_unsubscribing = False
        self.subscribed = False
