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
from driftpy.drift_user_stats import DriftUserStats, UserStatsSubscriptionConfig
from driftpy.memcmp import get_user_stats_filter
from driftpy.types import (
    NewUserRecord,
    DepositRecord,
    InsuranceFundStakeRecord,
    LPRecord,
    FundingPaymentRecord,
    LiquidationRecord,
    PickledData,
    SettlePnlRecord,
    OrderRecord,
    OrderActionRecord,
    UserStatsAccount,
    compress,
    decompress,
)
from driftpy.events.types import WrappedEvent
from driftpy.user_map.user_map_config import UserStatsMapConfig
from driftpy.user_map.user_map import UserMap
from driftpy.decode.user_stat import decode_user_stat


class UserStatsMap:
    def __init__(self, config: UserStatsMapConfig):
        self.user_stats_map: Dict[str, DriftUserStats] = {}

        self.sync_lock = asyncio.Lock()
        self.raw: Dict[str, bytes] = {}
        self.drift_client = config.drift_client
        self.latest_slot: int = 0
        self.last_dumped_slot: int = 0
        self.connection = config.connection or config.drift_client.connection

    async def subscribe(self):
        if self.size() > 0:
            return

        await self.drift_client.subscribe()

        await self.sync()

    async def sync(self):
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
                    [
                        str(self.drift_client.program_id),
                        {"filters": filters, "encoding": "base64", "withContext": True},
                    ],
                )

                post = self.connection._provider.session.post(
                    self.connection._provider.endpoint_uri,
                    json=rpc_request,
                    headers={"content-encoding": "gzip"},
                )

                resp = await asyncio.wait_for(post, timeout=10)

                parsed_resp = jsonrpcclient.parse(resp.json())

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
                        self.update_user_stat(pubkey, DataAndSlot(slot, data))

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
                data = decode_user_stat(decompress(user_stat.data))
                await self.add_user_stat(
                    Pubkey.from_string(str(user_stat.pubkey)), DataAndSlot(slot, data)
                )

    def dump(self):
        user_stats = []
        for _pubkey, user_stat in self.raw.items():
            decoded: UserStatsAccount = decode_user_stat(user_stat)
            auth = decoded.authority
            user_stats.append(PickledData(pubkey=auth, data=compress(user_stat)))
        self.last_dumped_slot = self.latest_slot
        filename = f"userstats_{self.last_dumped_slot}.pkl"
        with open(filename, "wb") as f:
            pickle.dump(user_stats, f, pickle.HIGHEST_PROTOCOL)
