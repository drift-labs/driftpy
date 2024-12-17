import asyncio
from base64 import b64decode
from dataclasses import dataclass
from typing import Callable, List, Optional

import jsonrpcclient
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solders.pubkey import Pubkey


@dataclass
class AccountToLoad:
    pubkey: Pubkey
    callbacks: dict[int, Callable[[bytes, int], None]]


@dataclass
class BufferAndSlot:
    slot: int
    buffer: Optional[bytes]


GET_MULTIPLE_ACCOUNTS_CHUNK_SIZE = 99


class BulkAccountLoader:
    def __init__(
        self,
        connection: AsyncClient,
        commitment: Commitment = "confirmed",
        frequency: float = 1,
    ):
        self.connection = connection
        self.commitment = commitment
        self.frequency = frequency
        self.task = None
        self.load_task = None
        self.callback_id = 0
        self.accounts_to_load: dict[str, AccountToLoad] = {}
        self.buffer_and_slot_map: dict[str, BufferAndSlot] = {}

    def add_account(
        self, pubkey: Pubkey, callback: Callable[[bytes, int], None]
    ) -> int:
        existing_size = len(self.accounts_to_load)

        callback_id = self.get_callback_id()

        pubkey_str = str(pubkey)
        existing_account_to_load = self.accounts_to_load.get(pubkey_str)
        if existing_account_to_load is not None:
            existing_account_to_load.callbacks[callback_id] = callback
        else:
            callbacks = {}
            callbacks[callback_id] = callback
            self.accounts_to_load[pubkey_str] = AccountToLoad(pubkey, callbacks)

        if existing_size == 0:
            self._start_loading()

        # If the account is already loaded, call the callback immediately
        if existing_account_to_load is not None:
            buffer_and_slot = self.buffer_and_slot_map.get(pubkey_str)
            if buffer_and_slot is not None and buffer_and_slot.buffer is not None:
                self.handle_callbacks(
                    existing_account_to_load,
                    buffer_and_slot.buffer,
                    buffer_and_slot.slot,
                )

        return callback_id

    def get_callback_id(self) -> int:
        self.callback_id += 1
        return self.callback_id

    def _start_loading(self):
        if self.task is None:

            async def loop():
                while True:
                    await self.load()
                    await asyncio.sleep(self.frequency)

            self.task = asyncio.create_task(loop())

    def remove_account(self, pubkey: Pubkey, callback_id: int):
        pubkey_str = str(pubkey)
        existing_account_to_load = self.accounts_to_load.get(pubkey_str)
        if existing_account_to_load is not None:
            del existing_account_to_load.callbacks[callback_id]
            if len(existing_account_to_load.callbacks) == 0:
                del self.accounts_to_load[pubkey_str]

        if len(self.accounts_to_load) == 0:
            self._stop_loading()

    def _stop_loading(self):
        if self.task is not None:
            self.task.cancel()
            self.task = None

    def chunks(self, array: List, size: int) -> List[List]:
        return [array[i : i + size] for i in range(0, len(array), size)]

    async def load(self):
        chunks = self.chunks(
            self.chunks(
                list(self.accounts_to_load.values()),
                GET_MULTIPLE_ACCOUNTS_CHUNK_SIZE,
            ),
            10,
        )

        await asyncio.gather(*[self.load_chunk(chunk) for chunk in chunks])

    async def load_chunk(self, chunk: List[List[AccountToLoad]]):
        if len(chunk) == 0:
            return

        rpc_requests = []
        for accounts_to_load in chunk:
            pubkeys_to_send = [
                str(accounts_to_load.pubkey) for accounts_to_load in accounts_to_load
            ]
            rpc_request = jsonrpcclient.request(
                "getMultipleAccounts",
                params=(
                    pubkeys_to_send,
                    {"encoding": "base64", "commitment": self.commitment},
                ),
            )
            rpc_requests.append(rpc_request)

        try:
            post = self.connection._provider.session.post(
                self.connection._provider.endpoint_uri,
                json=rpc_requests,
                headers={"content-encoding": "gzip"},
            )
            resp = await asyncio.wait_for(post, timeout=10)
        except asyncio.TimeoutError:
            print("request to rpc timed out")
            return

        parsed_resp = jsonrpcclient.parse(resp.json())

        if isinstance(parsed_resp, jsonrpcclient.Error):
            raise ValueError(f"Error fetching accounts: {parsed_resp.message}")
        if not isinstance(parsed_resp, jsonrpcclient.Ok):
            raise ValueError(f"Error fetching accounts - not ok: {parsed_resp}")

        for rpc_result, chunk_accounts in zip(parsed_resp, chunk):
            if isinstance(rpc_result, jsonrpcclient.Error):
                print(f"Failed to get info about accounts: {rpc_result.message}")
                continue

            slot = rpc_result.result["context"]["slot"]

            for i, account_to_load in enumerate(chunk_accounts):
                pubkey_str = str(account_to_load.pubkey)
                old_buffer_and_slot = self.buffer_and_slot_map.get(pubkey_str)

                if old_buffer_and_slot is not None and slot < old_buffer_and_slot.slot:
                    continue

                new_buffer = None
                if rpc_result.result["value"][i] is not None:
                    new_buffer = b64decode(rpc_result.result["value"][i]["data"][0])

                if (
                    old_buffer_and_slot is None
                    or new_buffer != old_buffer_and_slot.buffer
                ):
                    self.handle_callbacks(account_to_load, new_buffer, slot)
                    self.buffer_and_slot_map[pubkey_str] = BufferAndSlot(
                        slot, new_buffer
                    )

    def handle_callbacks(
        self, account_to_load: AccountToLoad, buffer: Optional[bytes], slot: int
    ):
        for cb in account_to_load.callbacks.values():
            if bytes is not None:
                cb(buffer, slot)
