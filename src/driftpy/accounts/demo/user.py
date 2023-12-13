from typing import Optional

from anchorpy import Program
from solders.pubkey import Pubkey
from solana.rpc.commitment import Commitment

from driftpy.accounts import get_user_account_and_slot
from driftpy.accounts import UserAccountSubscriber, DataAndSlot
from driftpy.types import UserAccount


class DemoUserAccountSubscriber(UserAccountSubscriber):
    def __init__(
        self,
        user_pubkey: Pubkey,
        program: Program,
        commitment: Commitment = "confirmed",
    ):
        self.program = program
        self.commitment = commitment
        self.user_pubkey = user_pubkey
        self.user_and_slot = None

    async def subscribe(self):
        await self.update_cache()

    async def update_cache(self):
        user_and_slot = await get_user_account_and_slot(self.program, self.user_pubkey)
        self.user_and_slot = user_and_slot

    async def fetch(self):
        await self.update_cache()

    def get_user_account_and_slot(self) -> Optional[DataAndSlot[UserAccount]]:
        return self.user_and_slot

    def unsubscribe(self):
        self.user_and_slot = None
