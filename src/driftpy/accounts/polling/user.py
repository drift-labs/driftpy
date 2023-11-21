import asyncio
from typing import Optional

from anchorpy import Program
from solders.pubkey import Pubkey

from driftpy.accounts import UserAccountSubscriber, DataAndSlot

from typing import Generic, TypeVar

from driftpy.accounts.bulk_account_loader import BulkAccountLoader
from driftpy.types import User

T = TypeVar("T")


class PollingUserAccountSubscriber(UserAccountSubscriber):
    def __init__(
        self,
        user_account_pubkey: Pubkey,
        program: Program,
        bulk_account_loader: BulkAccountLoader,
    ):
        self.bulk_account_loader = bulk_account_loader
        self.program = program
        self.user_account_pubkey = user_account_pubkey
        self.data_and_slot: Optional[DataAndSlot[User]] = None
        self.decode = self.program.coder.accounts.decode
        self.callback_id = None

    async def subscribe(self):
        if self.callback_id is not None:
            return

        self.add_to_account_loader()

        if self.data_and_slot is None:
            await self.fetch()

    def add_to_account_loader(self):
        if self.callback_id is not None:
            return

        self.callback_id = self.bulk_account_loader.add_account(
            self.user_account_pubkey, self._account_loader_callback
        )

    def _account_loader_callback(self, buffer: bytes, slot: int):
        if buffer is None:
            return

        if self.data_and_slot is not None and self.data_and_slot.slot >= slot:
            return

        account = self.decode(buffer)
        self.data_and_slot = DataAndSlot(slot, account)

    async def fetch(self):
        await self.bulk_account_loader.load()

    def _update_data(self, new_data: Optional[DataAndSlot[T]]):
        if new_data is None:
            return

        if self.data_and_slot is None or new_data.slot > self.data_and_slot.slot:
            self.data_and_slot = new_data

    def unsubscribe(self):
        if self.callback_id is None:
            return

        self.bulk_account_loader.remove_account(
            self.user_account_pubkey, self.callback_id
        )

        self.callback_id = None

    async def get_user_account_and_slot(self) -> Optional[DataAndSlot[User]]:
        return self.data_and_slot
