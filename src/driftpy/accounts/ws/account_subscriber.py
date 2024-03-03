import asyncio
import random

from typing import Optional, cast, Generic, TypeVar, Callable

from anchorpy import Program

from solders.pubkey import Pubkey  # type: ignore

from solana.rpc.commitment import Commitment
from solana.rpc.websocket_api import connect, SolanaWsClientProtocol

from driftpy.accounts import get_account_data_and_slot
from driftpy.accounts import UserAccountSubscriber, DataAndSlot
from driftpy.types import get_ws_url

T = TypeVar("T")

MAX_FAILURES = 10
MAX_DELAY = 16


class WebsocketAccountSubscriber(UserAccountSubscriber, Generic[T]):
    def __init__(
        self,
        pubkey: Pubkey,
        program: Program,
        commitment: Commitment = "confirmed",
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
        self.ws = None

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
        num_failures = 0
        delay = 1
        while True:
            try:
                async with connect(ws_endpoint) as ws:
                    self.ws = ws
                    ws: SolanaWsClientProtocol

                    await ws.account_subscribe(
                        self.pubkey, commitment=self.commitment, encoding="base64"
                    )

                    await ws.recv()

                    async for msg in ws:
                        slot = int(msg[0].result.context.slot)  # type: ignore

                        if msg[0].result.value is None:
                            continue

                        account_bytes = cast(bytes, msg[0].result.value.data)  # type: ignore
                        decoded_data = self.decode(account_bytes)
                        self.update_data(DataAndSlot(slot, decoded_data))
            except Exception as e:
                print(f"Error in websocket subscription: {e}")
                num_failures += 1
                if num_failures > MAX_FAILURES:
                    print(
                        f"Max failures reached for subscription: {self.pubkey}, unsubscribing"
                    )
                    await self.unsubscribe()
                    break
                if self.ws:
                    await self.ws.close()
                    self.ws = None
                await asyncio.sleep(
                    delay
                )  # wait a second before we retry, exponential backoff
                delay = min(delay * 2, MAX_DELAY)
                delay += delay * random.uniform(-0.1, 0.1)  # add some jitter

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
