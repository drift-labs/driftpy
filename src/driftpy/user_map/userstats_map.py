import asyncio
import base64
import os
import pickle
import traceback
from typing import Dict, Optional

import jsonrpcclient
from solders.pubkey import Pubkey

from driftpy.accounts.types import DataAndSlot
from driftpy.addresses import get_user_stats_account_public_key
from driftpy.decode.user_stat import decode_user_stat
from driftpy.drift_user_stats import DriftUserStats, UserStatsSubscriptionConfig
from driftpy.events.types import WrappedEvent
from driftpy.memcmp import get_user_stats_filter
from driftpy.types import (
    DepositRecord,
    FundingPaymentRecord,
    InsuranceFundStakeRecord,
    LiquidationRecord,
    LPRecord,
    NewUserRecord,
    OrderActionRecord,
    OrderRecord,
    PickledData,
    SettlePnlRecord,
    UserStatsAccount,
    compress,
    decompress,
)
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import SyncConfig, UserStatsMapConfig


class UserStatsMap:
    def __init__(self, config: UserStatsMapConfig):
        self.user_stats_map: Dict[str, DriftUserStats] = {}

        self.sync_lock = asyncio.Lock()
        self.raw: Dict[str, bytes] = {}
        self.drift_client = config.drift_client
        self.latest_slot: int = 0
        self.last_dumped_slot: int = 0
        self.connection = config.connection or config.drift_client.connection
        self.sync_config = config.sync_config or SyncConfig(type="default")

    async def subscribe(self):
        if self.size() > 0:
            return

        await self.drift_client.subscribe()

        await self.sync()

    async def sync(self):
        if self.sync_config.type == "default":
            return await self.default_sync()
        else:
            return await self.paginated_sync()

    async def default_sync(self):
        async with self.sync_lock:
            try:
                filters = [
                    {
                        "memcmp": {
                            "offset": 0,
                            "bytes": f"{get_user_stats_filter().bytes}",
                        }
                    }
                ]

                rpc_request = jsonrpcclient.request(
                    "getProgramAccounts",
                    (
                        str(self.drift_client.program_id),
                        {"filters": filters, "encoding": "base64", "withContext": True},
                    ),
                )

                post = self.connection._provider.session.post(
                    self.connection._provider.endpoint_uri,
                    json=rpc_request,
                    headers={"content-encoding": "gzip"},
                )

                resp = await asyncio.wait_for(post, timeout=120)

                parsed_resp = jsonrpcclient.parse(resp.json())
                if isinstance(parsed_resp, jsonrpcclient.Error):
                    raise ValueError(
                        f"Error fetching user stats: {parsed_resp.message}"
                    )

                if not isinstance(parsed_resp, jsonrpcclient.Ok):
                    raise ValueError(
                        f"Error fetching user stats - not ok: {parsed_resp}"
                    )

                slot = int(parsed_resp.result["context"]["slot"])

                self.latest_slot = slot

                rpc_response_values = parsed_resp.result["value"]

                program_account_buffer_map: Dict[str, UserStatsAccount] = {}
                raw: Dict[str, bytes] = {}

                for program_account in rpc_response_values:
                    pubkey = program_account["pubkey"]
                    buffer = base64.b64decode(program_account["account"]["data"][0])
                    data = decode_user_stat(buffer)
                    program_account_buffer_map[str(pubkey)] = data
                    raw[str(pubkey)] = buffer

                self.raw = raw

                for pubkey in program_account_buffer_map.keys():
                    data = program_account_buffer_map.get(pubkey)
                    if not self.has(pubkey):
                        await self.add_user_stat(
                            Pubkey.from_string(pubkey), DataAndSlot(slot, data)
                        )
                    else:
                        await self.update_user_stat(pubkey, DataAndSlot(slot, data))

                    await asyncio.sleep(0)

                keys_to_delete = []
                for key in list(self.user_stats_map.keys()):
                    if key not in program_account_buffer_map:
                        keys_to_delete.append(key)
                    await asyncio.sleep(0)

                for key in keys_to_delete:
                    del self.user_stats_map[key]

            except Exception as e:
                print(f"Error in UserStatsMap.sync(): {e}")
                traceback.print_exc()

    async def paginated_sync(self):
        async with self.sync_lock:
            try:
                if not hasattr(self, "sync_promise"):
                    self.sync_promise = None

                if self.sync_promise:
                    return await self.sync_promise

                self.sync_promise = asyncio.Future()

                try:
                    filters = [
                        {
                            "memcmp": {
                                "offset": 0,
                                "bytes": f"{get_user_stats_filter().bytes}",
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
                                "dataSlice": {"offset": 0, "length": 0},
                            },
                        ),
                    )

                    post = self.connection._provider.session.post(
                        self.connection._provider.endpoint_uri,
                        json=rpc_request,
                        headers={"content-encoding": "gzip"},
                    )

                    resp = await asyncio.wait_for(post, timeout=120)
                    parsed_resp = jsonrpcclient.parse(resp.json())

                    if isinstance(parsed_resp, jsonrpcclient.Error):
                        raise ValueError(
                            f"Error fetching user stats pubkeys: {parsed_resp.message}"
                        )

                    accounts_to_load = [
                        account["pubkey"] for account in parsed_resp.result
                    ]

                    chunk_size = self.sync_config.chunk_size or 100
                    concurrency_limit = self.sync_config.concurrency_limit or 10

                    semaphore = asyncio.Semaphore(concurrency_limit)
                    slot = 0

                    async def process_chunk(chunk):
                        nonlocal slot

                        async with semaphore:
                            # Request multiple accounts at once
                            rpc_request = jsonrpcclient.request(
                                "getMultipleAccounts",
                                (
                                    chunk,
                                    {
                                        "encoding": "base64",
                                        "commitment": "confirmed",
                                    },
                                ),
                            )

                            post = self.connection._provider.session.post(
                                self.connection._provider.endpoint_uri,
                                json=rpc_request,
                            )

                            resp = await asyncio.wait_for(post, timeout=120)
                            parsed_resp = jsonrpcclient.parse(resp.json())

                            if isinstance(parsed_resp, jsonrpcclient.Error):
                                raise ValueError(
                                    f"Error fetching multiple accounts: {parsed_resp.message}"
                                )

                            slot = int(parsed_resp.result["context"]["slot"])
                            program_account_buffer_map = set()

                            for i, account_info in enumerate(
                                parsed_resp.result["value"]
                            ):
                                if account_info is None:
                                    continue

                                buffer = base64.b64decode(account_info["data"][0])
                                decoded_user_stats = decode_user_stat(buffer)

                                authority = str(decoded_user_stats.authority)
                                program_account_buffer_map.add(authority)

                                if not self.has(authority):
                                    await self.add_user_stat(
                                        decoded_user_stats.authority,
                                        DataAndSlot(slot, decoded_user_stats),
                                    )

                            return program_account_buffer_map

                    tasks = []
                    for i in range(0, len(accounts_to_load), chunk_size):
                        chunk = accounts_to_load[i : i + chunk_size]
                        tasks.append(process_chunk(chunk))

                    results = await asyncio.gather(*tasks)

                    all_account_buffer_map = set()
                    for account_set in results:
                        all_account_buffer_map.update(account_set)

                    keys_to_delete = []
                    for key in self.user_stats_map.keys():
                        if key not in all_account_buffer_map:
                            keys_to_delete.append(key)

                    for key in keys_to_delete:
                        user = self.get(key)
                        if user:
                            user.unsubscribe()
                            del self.user_stats_map[key]

                    self.latest_slot = slot

                except Exception as e:
                    print(f"Error in UserStatsMap.paginated_sync(): {e}")
                    traceback.print_exc()

                finally:
                    self.sync_promise.set_result(None)
                    self.sync_promise = None

            except Exception as e:
                print(f"Error in UserStatsMap.paginated_sync(): {e}")
                traceback.print_exc()

    def unsubscribe(self):
        keys = list(self.user_stats_map.keys())
        for key in keys:
            self.user_stats_map[key].unsubscribe()
            del self.user_stats_map[key]

    async def add_user_stat(
        self,
        authority: Pubkey,
        user_stats: Optional[DataAndSlot[UserStatsAccount]] = None,
    ):
        user_stat = DriftUserStats(
            self.drift_client,
            get_user_stats_account_public_key(self.drift_client.program_id, authority),
            UserStatsSubscriptionConfig(initial_data=user_stats),
        )
        self.user_stats_map[str(authority)] = user_stat

    async def update_user_stat(
        self, authority: Pubkey, user_stats: DataAndSlot[UserStatsAccount]
    ):
        await self.must_get(str(authority), user_stats)
        self.user_stats_map[str(authority)] = user_stats

    async def update_with_order_record(self, record: OrderRecord, user_map: UserMap):
        user = await user_map.must_get(str(record.user))
        await self.must_get(str(user.get_user_account().authority))

    async def update_with_event_record(
        self, record: WrappedEvent, user_map: Optional[UserMap] = None
    ):
        if record.event_type == "DepositRecord":
            deposit_record: DepositRecord = record
            await self.must_get(str(deposit_record.user_authority))

        elif record.event_type == "FundingPaymentRecord":
            funding_payment_record: FundingPaymentRecord = record
            await self.must_get(str(funding_payment_record.user_authority))

        elif record.event_type == "LiquidationRecord":
            if not user_map:
                return

            liq_record: LiquidationRecord = record

            user = await user_map.must_get(str(liq_record.user))
            await self.must_get(str(user.get_user_account().authority))

            liquidator = await user_map.must_get(str(liq_record.liquidator))
            await self.must_get(str(liquidator.get_user_account().authority))

        elif record.event_type == "OrderRecord":
            if not user_map:
                return

            order_record: OrderRecord = record
            await user_map.update_with_order_record(order_record)

        elif record.event_type == "OrderActionRecord":
            if not user_map:
                return

            action_record: OrderActionRecord = record

            if action_record.taker:
                taker = await user_map.must_get(str(action_record.taker))
                await self.must_get(str(taker.get_user_account().authority))

            if action_record.maker:
                maker = await user_map.must_get(str(action_record.maker))
                await self.must_get(str(maker.get_user_account().authority))

        elif record.event_type == "SettlePnlRecord":
            if not user_map:
                return

            settle_record: SettlePnlRecord = record

            user = await user_map.must_get(str(settle_record.user))
            await self.must_get(str(user.get_user_account().authority))

        elif record.event_type == "NewUserRecord":
            new_user_record: NewUserRecord = record

            await self.must_get(str(new_user_record.user_authority))

        elif record.event_type == "LPRecord":
            if not user_map:
                return

            lp_record: LPRecord = record

            user = await user_map.must_get(str(lp_record.user))
            await self.must_get(str(user.get_user_account().authority))

        elif record.event_type == "InsuranceFundStakeRecord":
            stake_record: InsuranceFundStakeRecord = record

            await self.must_get(str(stake_record.authority))

    def values(self):
        return self.user_stats_map.values()

    def size(self):
        return len(self.user_stats_map)

    def has(self, pubkey: str) -> bool:
        return pubkey in self.user_stats_map

    def get(self, pubkey: str):
        return self.user_stats_map.get(pubkey)

    async def must_get(
        self, pubkey: str, user_stats: Optional[DataAndSlot[UserStatsAccount]] = None
    ):
        if not self.has(pubkey):
            await self.add_user_stat(Pubkey.from_string(pubkey), user_stats)
        return self.get(pubkey)

    def get_last_dump_filepath(self) -> str:
        return f"userstats_{self.last_dumped_slot}.pkl"

    def clear(self):
        self.user_stats_map.clear()

    async def load(self, filename: Optional[str] = None):
        if not filename:
            filename = self.get_last_dump_filepath()
        if not os.path.exists(filename):
            raise FileNotFoundError(f"File {filename} not found")
        start = filename.index("_") + 1
        end = filename.index(".")
        slot = int(filename[start:end])
        with open(filename, "rb") as f:
            user_stats: list[PickledData] = pickle.load(f)
            for user_stat in user_stats:
                decompressed_data = decompress(user_stat.data)
                data = decode_user_stat(decompressed_data)
                await self.add_user_stat(
                    Pubkey.from_string(str(user_stat.pubkey)), DataAndSlot(slot, data)
                )

    def dump(self, filename: Optional[str] = None):
        user_stats = []
        for _pubkey, user_stat in self.raw.items():
            decoded: UserStatsAccount = decode_user_stat(user_stat)
            auth = decoded.authority
            user_stats.append(PickledData(pubkey=auth, data=compress(user_stat)))
        self.last_dumped_slot = self.latest_slot
        path = filename or f"userstats_{self.last_dumped_slot}.pkl"
        with open(path, "wb") as f:
            pickle.dump(user_stats, f, pickle.HIGHEST_PROTOCOL)
