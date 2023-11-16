from typing import Optional

from anchorpy import Program
from solana.publickey import PublicKey
from solana.rpc.commitment import Commitment

from driftpy.accounts import get_user_account_and_slot
from driftpy.accounts import UserAccountSubscriber, DataAndSlot
from driftpy.types import User


class CachedUserAccountSubscriber(UserAccountSubscriber):
    def __init__(self, user_pubkey: PublicKey, program: Program, commitment: Commitment = "confirmed"):
        self.program = program
        self.commitment = commitment
        self.user_pubkey = user_pubkey
        self.user_and_slot = None

    async def update_cache(self):
        user_and_slot = await get_user_account_and_slot(self.program, self.user_pubkey)
        self.user_and_slot = user_and_slot

    async def get_user_account_and_slot(self) -> Optional[DataAndSlot[User]]:
        await self.cache_if_needed()
        return self.user_and_slot

    async def cache_if_needed(self):
        if self.user_and_slot is None:
            await self.update_cache()
