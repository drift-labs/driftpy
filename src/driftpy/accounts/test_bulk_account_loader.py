from base64 import b64decode
from typing import List, Optional

from driftpy.accounts.bulk_account_loader import (
    AccountToLoad,
    BufferAndSlot,
    BulkAccountLoader,
)


class TestBulkAccountLoader(BulkAccountLoader):
    async def load_chunk(
        self, accounts_to_load_chunks: List[List[AccountToLoad]]
    ) -> None:
        if len(accounts_to_load_chunks) == 0:
            return

        for accounts_to_load_chunk in accounts_to_load_chunks:
            for account_to_load in accounts_to_load_chunk:
                account = await self.connection.get_account_info(
                    account_to_load.pubkey, commitment=self.commitment
                )
                new_slot = account.context.slot
                if new_slot > self.most_recent_slot:
                    self.most_recent_slot = new_slot

                if len(account_to_load.callbacks) == 0:
                    continue

                pubkey_str = str(account_to_load.pubkey)
                prev = self.buffer_and_slot_map.get(pubkey_str)

                if prev and new_slot < prev.slot:
                    continue

                new_buffer: Optional[bytes] = None
                if account.value:
                    if isinstance(account.value.data, bytes):
                        new_buffer = account.value.data
                    else:
                        new_buffer = b64decode(
                            account.value.data + b"=" * (-len(account.value.data) % 4)
                        )

                if not prev:
                    self.buffer_and_slot_map[pubkey_str] = BufferAndSlot(
                        slot=new_slot, buffer=new_buffer
                    )
                    self.handle_callbacks(account_to_load, new_buffer, new_slot)
                    return

                if new_buffer != prev.buffer:
                    self.buffer_and_slot_map[pubkey_str] = BufferAndSlot(
                        slot=new_slot, buffer=new_buffer
                    )
                    self.handle_callbacks(account_to_load, new_buffer, new_slot)
