import asyncio
import base64
from typing import Dict, Optional

import jsonrpcclient
from solana.rpc.types import MemcmpOpts
from solders.pubkey import Pubkey

from driftpy.addresses import (
    get_user_account_public_key,
    get_user_stats_account_public_key,
)
from driftpy.drift_client import DriftClient
from driftpy.memcmp import (
    get_user_stats_filter,
    get_user_stats_is_referred_filter,
    get_user_stats_is_referred_or_referrer_filter,
)
from driftpy.types import ReferrerInfo

DEFAULT_PUBLIC_KEY = str(Pubkey.default())


class ReferrerMap:
    authority_referrer_map: Dict[str, str]
    referrer_referrer_info_map: Dict[str, ReferrerInfo]
    drift_client: DriftClient
    parallel_sync: bool
    fetch_lock: asyncio.Lock
    is_syncing: bool
    initial_load_finished: asyncio.Event
    chunk_size: int
    max_concurrent_requests: int

    def __init__(
        self,
        drift_client: DriftClient,
        parallel_sync: Optional[bool] = True,
        chunk_size: int = 100,
        max_concurrent_requests: int = 5,
        verbose: bool = False,
    ):
        self.drift_client = drift_client
        self.parallel_sync = parallel_sync
        self.authority_referrer_map = {}
        self.referrer_referrer_info_map = {}
        self.fetch_lock = asyncio.Lock()
        self.is_syncing = False
        self.initial_load_finished = asyncio.Event()
        self.chunk_size = chunk_size
        self.max_concurrent_requests = max_concurrent_requests
        self.verbose = verbose

    def log(self, message: str):
        if self.verbose:
            print(f"[ReferrerMap] {message}")

    async def subscribe(self):
        self.log(f"subscribe() called, current size: {self.size()}")
        if self.size() > 0:
            self.log(
                f"[ReferrerMap] Already has {self.size()} entries, skipping subscribe"
            )
            return

        self.log("Starting drift client subscribe...")
        await self.drift_client.subscribe()
        self.log("Starting sync...")
        await self.sync()
        self.log(f"Subscribe complete, final size: {self.size()}")

    def has(self, authority_public_key: str) -> bool:
        return authority_public_key in self.authority_referrer_map

    def get(self, authority_public_key: str) -> Optional[ReferrerInfo]:
        return self.get_referrer(authority_public_key)

    def get_referrer(self, authority_public_key: str) -> Optional[ReferrerInfo]:
        referrer = self.authority_referrer_map.get(authority_public_key)
        if referrer is None:
            self.log(
                f"[ReferrerMap] No referrer found for authority {authority_public_key[:8]}..."
            )
            return None

        if referrer == DEFAULT_PUBLIC_KEY:
            self.log(
                f"[ReferrerMap] Authority {authority_public_key[:8]}... has no referrer (default)"
            )
            return None

        if referrer in self.referrer_referrer_info_map:
            self.log(
                f"[ReferrerMap] Returning cached referrer info for {authority_public_key[:8]}... -> {referrer[:8]}..."
            )
            return self.referrer_referrer_info_map[referrer]

        self.log(
            f"[ReferrerMap] Creating new referrer info for {authority_public_key[:8]}... -> {referrer[:8]}..."
        )
        referrer_key = Pubkey.from_string(referrer)
        referrer_info = ReferrerInfo(
            referrer=get_user_account_public_key(
                self.drift_client.program_id, referrer_key, 0
            ),
            referrer_stats=get_user_stats_account_public_key(
                self.drift_client.program_id, referrer_key
            ),
        )

        self.referrer_referrer_info_map[referrer] = referrer_info
        return referrer_info

    def size(self) -> int:
        return len(self.authority_referrer_map)

    def number_of_referred(self) -> int:
        return len(
            [r for r in self.authority_referrer_map.values() if r != DEFAULT_PUBLIC_KEY]
        )

    async def add_referrer(self, authority: str, referrer: Optional[str] = None):
        if referrer is not None:
            self.authority_referrer_map[authority] = referrer
        else:
            self.log(f"Fetching referrer for authority: {authority[:8]}...")
            user_stats_account_public_key = get_user_stats_account_public_key(
                self.drift_client.program_id, Pubkey.from_string(authority)
            )
            account_info = await self.drift_client.connection.get_account_info(
                user_stats_account_public_key
            )
            if account_info.value is None:
                self.log(
                    f"[ReferrerMap] No user stats account found for {authority[:8]}..., using default"
                )
                # Or if there's no user stats account, this user wasn't referred by anyone
                self.authority_referrer_map[authority] = DEFAULT_PUBLIC_KEY
                return

            buffer = account_info.value.data
            referrer_bytes = buffer[40:72]
            decoded_referrer = str(Pubkey(referrer_bytes))
            self.log(
                f"[ReferrerMap] Found referrer for {authority[:8]}...: {decoded_referrer[:8]}..."
            )
            self.authority_referrer_map[authority] = decoded_referrer

    async def must_get(self, authority_public_key: str) -> Optional[ReferrerInfo]:
        if not self.has(authority_public_key):
            await self.add_referrer(authority_public_key)
        return self.get_referrer(authority_public_key)

    async def sync(self) -> None:
        if self.is_syncing:
            self.log("Already syncing, waiting for completion...")
            await self.initial_load_finished.wait()
            return

        async with self.fetch_lock:
            self.log(
                f"[ReferrerMap] Starting sync (parallel_sync={self.parallel_sync})..."
            )
            self.is_syncing = True
            try:
                if self.parallel_sync:
                    self.log("Running parallel sync tasks...")
                    # Use a semaphore to limit concurrent requests
                    semaphore = asyncio.Semaphore(self.max_concurrent_requests)
                    await asyncio.gather(
                        self.sync_all_paged(semaphore),
                        self.sync_referrer_paged(
                            get_user_stats_is_referred_filter(), semaphore
                        ),
                        self.sync_referrer_paged(
                            get_user_stats_is_referred_or_referrer_filter(), semaphore
                        ),
                    )
                else:
                    self.log("Running sequential sync tasks...")
                    await self.sync_all()
                    await self.sync_referrer(get_user_stats_is_referred_filter())
                    await self.sync_referrer(
                        get_user_stats_is_referred_or_referrer_filter()
                    )
                self.log(
                    f"[ReferrerMap] Sync complete! Final stats: {self.size()} total users, {self.number_of_referred()} referred"
                )
            finally:
                self.is_syncing = False
                self.initial_load_finished.set()

    async def sync_all(self) -> None:
        self.log("sync_all() fast path starting...")
        drift_user_stats_filter = get_user_stats_filter()
        filters = [
            {
                "memcmp": {
                    "offset": drift_user_stats_filter.offset,
                    "bytes": drift_user_stats_filter.bytes,
                }
            }
        ]

        rpc_request = jsonrpcclient.request(
            "getProgramAccounts",
            (
                str(self.drift_client.program_id),
                {
                    "filters": filters,
                    "encoding": "base64",
                    "dataSlice": {"offset": 8, "length": 32},  # authority only
                    "withContext": True,
                    "commitment": str(
                        self.drift_client.tx_sender.connection.commitment
                    ),
                },
            ),
        )

        post = self.drift_client.connection._provider.session.post(
            self.drift_client.connection._provider.endpoint_uri,
            json=rpc_request,
        )

        resp = await asyncio.wait_for(post, timeout=120)
        parsed_resp = jsonrpcclient.parse(resp.json())

        if isinstance(parsed_resp, jsonrpcclient.Error):
            raise ValueError(
                f"Error fetching user stats authorities: {parsed_resp.message}"
            )

        result = parsed_resp.result
        value = (
            result["value"]
            if isinstance(result, dict) and "value" in result
            else result
        )
        if not value:
            self.log("No user stats accounts found")
            return

        new_users = 0
        for acc in value:
            buf_b64 = acc["account"]["data"][0]
            decoded = base64.b64decode(buf_b64)
            authority = str(Pubkey(decoded[0:32]))
            if not self.has(authority):
                await self.add_referrer(authority, DEFAULT_PUBLIC_KEY)
                new_users += 1
        self.log(f"sync_all() fast path complete: added {new_users} new users")

    async def sync_referrer(self, referrer_filter) -> None:
        self.log(
            f"[ReferrerMap] sync_referrer() starting with filter offset {referrer_filter.offset}..."
        )
        drift_user_stats_filter = get_user_stats_filter()
        filters = [
            MemcmpOpts(
                offset=drift_user_stats_filter.offset,
                bytes=drift_user_stats_filter.bytes,
            ),
            MemcmpOpts(offset=referrer_filter.offset, bytes=referrer_filter.bytes),
        ]

        self.log("Fetching referrer accounts...")
        response = await self.drift_client.connection.get_program_accounts(
            pubkey=self.drift_client.program_id,
            encoding="base64",
            data_slice=None,
            filters=filters,
            commitment=self.drift_client.tx_sender.connection.commitment,
        )

        if response.value is None:
            self.log("No referrer accounts found")
            return

        self.log(f"Found {len(response.value)} accounts with referrer data")
        for program_account in response.value:
            buffer = program_account.account.data
            authority = str(Pubkey(buffer[8:40]))
            referrer = str(Pubkey(buffer[40:72]))
            await self.add_referrer(authority, referrer)
            await asyncio.sleep(0)
        self.log(
            f"[ReferrerMap] sync_referrer() complete for filter offset {referrer_filter.offset}"
        )

    async def sync_all_paged(self, semaphore: asyncio.Semaphore) -> None:
        self.log("sync_all_paged() fast path starting...")
        drift_user_stats_filter = get_user_stats_filter()
        filters = [
            {
                "memcmp": {
                    "offset": drift_user_stats_filter.offset,
                    "bytes": drift_user_stats_filter.bytes,
                }
            }
        ]

        async with semaphore:
            rpc_request = jsonrpcclient.request(
                "getProgramAccounts",
                (
                    str(self.drift_client.program_id),
                    {
                        "filters": filters,
                        "encoding": "base64",
                        "dataSlice": {"offset": 8, "length": 32},
                        "withContext": True,
                        "commitment": str(
                            self.drift_client.tx_sender.connection.commitment
                        ),
                    },
                ),
            )

            post = self.drift_client.connection._provider.session.post(
                self.drift_client.connection._provider.endpoint_uri,
                json=rpc_request,
            )

            resp = await asyncio.wait_for(post, timeout=120)
            parsed_resp = jsonrpcclient.parse(resp.json())

            if isinstance(parsed_resp, jsonrpcclient.Error):
                raise ValueError(
                    f"Error fetching user stats authorities: {parsed_resp.message}"
                )

            result = parsed_resp.result
            value = (
                result["value"]
                if isinstance(result, dict) and "value" in result
                else result
            )
            if not value:
                self.log("No user stats accounts found")
                return

            new_users = 0
            for acc in value:
                buf_b64 = acc["account"]["data"][0]
                decoded = base64.b64decode(buf_b64)
                authority = str(Pubkey(decoded[0:32]))
                if not self.has(authority):
                    await self.add_referrer(authority, DEFAULT_PUBLIC_KEY)
                    new_users += 1

            self.log(
                f"sync_all_paged() fast path complete: added {new_users} new users"
            )

    async def sync_referrer_paged(
        self, referrer_filter, semaphore: asyncio.Semaphore
    ) -> None:
        self.log(
            f"[ReferrerMap] sync_referrer_paged() starting with filter offset {referrer_filter.offset}..."
        )

        async with semaphore:
            drift_user_stats_filter = get_user_stats_filter()
            filters = [
                {
                    "memcmp": {
                        "offset": drift_user_stats_filter.offset,
                        "bytes": drift_user_stats_filter.bytes,
                    }
                },
                {
                    "memcmp": {
                        "offset": referrer_filter.offset,
                        "bytes": referrer_filter.bytes,
                    }
                },
            ]

            rpc_request = jsonrpcclient.request(
                "getProgramAccounts",
                (
                    str(self.drift_client.program_id),
                    {
                        "filters": filters,
                        "encoding": "base64",
                        "dataSlice": {"offset": 0, "length": 72},
                        "withContext": True,
                        "commitment": str(
                            self.drift_client.tx_sender.connection.commitment
                        ),
                    },
                ),
            )

            post = self.drift_client.connection._provider.session.post(
                self.drift_client.connection._provider.endpoint_uri,
                json=rpc_request,
                headers={"content-encoding": "gzip"},
            )

            resp = await asyncio.wait_for(post, timeout=120)
            parsed_resp = jsonrpcclient.parse(resp.json())

            if isinstance(parsed_resp, jsonrpcclient.Error):
                raise ValueError(
                    f"Error fetching referrer accounts: {parsed_resp.message}"
                )

            result = parsed_resp.result
            value = (
                result["value"]
                if isinstance(result, dict) and "value" in result
                else result
            )
            if not value:
                self.log("No referrer accounts found")
                return

            self.log(f"Found {len(value)} accounts with referrer data")

            batch_size = 1000
            for i in range(0, len(value), batch_size):
                for account_data in value[i : i + batch_size]:
                    buffer_b64 = account_data["account"]["data"][0]
                    decoded_buffer = base64.b64decode(buffer_b64)
                    authority = str(Pubkey(decoded_buffer[8:40]))
                    referrer = str(Pubkey(decoded_buffer[40:72]))
                    await self.add_referrer(authority, referrer)
                await asyncio.sleep(0)

            self.log(
                f"[ReferrerMap] sync_referrer_paged() complete for filter offset {referrer_filter.offset}"
            )

    async def unsubscribe(self) -> None:
        self.authority_referrer_map.clear()
        self.referrer_referrer_info_map.clear()
        self.initial_load_finished.clear()
