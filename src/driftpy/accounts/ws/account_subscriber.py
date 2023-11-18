import asyncio
from typing import Optional

from anchorpy import Program
from solders.pubkey import Pubkey
from solana.rpc.commitment import Commitment

from driftpy.accounts import get_account_data_and_slot
from driftpy.accounts import UserAccountSubscriber, DataAndSlot

import websockets
import websockets.exceptions  # force eager imports
from solana.rpc.websocket_api import connect

from typing import cast, Generic, TypeVar, Callable

T = TypeVar("T")


class WebsocketAccountSubscriber(UserAccountSubscriber, Generic[T]):
    def __init__(
        self,
        pubkey: Pubkey,
        program: Program,
        commitment: Commitment = "confirmed",
        decode: Optional[Callable[[bytes], T]] = None,
    ):
        self.program = program
        self.commitment = commitment
        self.pubkey = pubkey
        self.data_and_slot = None
        self.task = None
        self.decode = (
            decode if decode is not None else self.program.coder.accounts.decode
        )

    async def subscribe(self):
        if self.data_and_slot is None:
            await self.fetch()

        self.task = asyncio.create_task(self.subscribe_ws())
        return self.task

    async def subscribe_ws(self):
        ws_endpoint = self.program.provider.connection._provider.endpoint_uri.replace(
            "https", "wss"
        ).replace("http", "ws")
        async for ws in connect(ws_endpoint):
            try:
                await ws.account_subscribe(  # type: ignore
                    self.pubkey,
                    commitment=self.commitment,
                    encoding="base64",
                )
                first_resp = await ws.recv()
                subscription_id = cast(int, first_resp[0].result)  # type: ignore

                async for msg in ws:
                    try:
                        slot = int(msg[0].result.context.slot)  # type: ignore

                        if msg[0].result.value is None:
                            continue

                        account_bytes = cast(bytes, msg[0].result.value.data)  # type: ignore
                        decoded_data = self.decode(account_bytes)
                        self._update_data(DataAndSlot(slot, decoded_data))
                    except Exception:
                        print(f"Error processing account data")
                        break
                await ws.account_unsubscribe(subscription_id)  # type: ignore
            except websockets.exceptions.ConnectionClosed:
                print("Websocket closed, reconnecting...")
                continue

    async def fetch(self):
        new_data = await get_account_data_and_slot(
            self.pubkey, self.program, self.commitment, self.decode
        )

        self._update_data(new_data)

    def _update_data(self, new_data: Optional[DataAndSlot[T]]):
        if new_data is None:
            return

        if self.data_and_slot is None or new_data.slot > self.data_and_slot.slot:
            self.data_and_slot = new_data

    def unsubscribe(self):
        self.task.cancel()
        self.task = None
