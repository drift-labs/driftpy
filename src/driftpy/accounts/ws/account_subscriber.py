import asyncio
from typing import Callable, Generic, Optional, TypeVar, cast

import websockets
import websockets.exceptions  # force eager imports
from anchorpy.program.core import Program
from solana.rpc.commitment import Commitment
from solana.rpc.websocket_api import SolanaWsClientProtocol, connect
from solders.pubkey import Pubkey

from driftpy.accounts import (
    DataAndSlot,
    UserAccountSubscriber,
    UserStatsAccountSubscriber,
    get_account_data_and_slot,
)
from driftpy.types import get_ws_url

T = TypeVar("T")


class WebsocketAccountSubscriber(
    UserAccountSubscriber, UserStatsAccountSubscriber, Generic[T]
):
    def __init__(
        self,
        pubkey: Pubkey,
        program: Program,
        commitment: Commitment = Commitment("confirmed"),
        decode: Optional[Callable[[bytes], T]] = None,
        initial_data: Optional[DataAndSlot] = None,
    ):
        self.program = program
        self.commitment = commitment
        self.pubkey = pubkey
        self.data_and_slot = initial_data or None
        self.task = None
        self.decode = (
            decode if decode is not None else self.program.coder.accounts.decode
        )
        self.ws: Optional[SolanaWsClientProtocol] = None

    async def subscribe(self):
        if self.data_and_slot is None:
            await self.fetch()

        self.task = asyncio.create_task(self.subscribe_ws())
        return self.task

    def is_subscribed(self):
        return self.task is not None

    async def subscribe_ws(self):
        endpoint = self.program.provider.connection._provider.endpoint_uri
        ws_endpoint = get_ws_url(endpoint)

        async for ws in connect(ws_endpoint):
            try:
                self.ws = cast(SolanaWsClientProtocol, ws)
                await self.ws.account_subscribe(
                    self.pubkey,
                    commitment=self.commitment,
                    encoding="base64",
                )
                first_resp = await ws.recv()
                subscription_id = cast(int, first_resp[0].result)

                async for msg in ws:
                    try:
                        slot = int(msg[0].result.context.slot)  # type: ignore

                        if msg[0].result.value is None:
                            continue

                        account_bytes = cast(bytes, msg[0].result.value.data)  # type: ignore
                        decoded_data = self.decode(account_bytes)
                        self.update_data(DataAndSlot(slot, decoded_data))
                    except Exception:
                        print("Error processing account data")
                        break
                await self.ws.account_unsubscribe(subscription_id)
            except websockets.exceptions.ConnectionClosed:
                print("Websocket closed, reconnecting...")
                continue

    async def fetch(self):
        new_data = await get_account_data_and_slot(
            self.pubkey, self.program, self.commitment, self.decode
        )
        self.update_data(new_data)

    def update_data(self, new_data: Optional[DataAndSlot[T]]):
        if new_data is None:
            return

        if self.data_and_slot is None or new_data.slot >= self.data_and_slot.slot:
            self.data_and_slot = new_data

    async def unsubscribe(self):
        if self.task:
            self.task.cancel()
            self.task = None
        if self.ws:
            await self.ws.close()
            self.ws = None
