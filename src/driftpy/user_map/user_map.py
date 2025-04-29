import asyncio
import base64
import os
import pickle
from typing import Any, Container, Dict, Optional

import jsonrpcclient
from solana.rpc.commitment import Confirmed
from solders.pubkey import Pubkey

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.accounts.types import DataAndSlot
from driftpy.decode.user import decode_user
from driftpy.dlob.client_types import DLOBSource
from driftpy.drift_client import DriftClient
from driftpy.drift_user import DriftUser
from driftpy.types import OrderRecord, PickledData, UserAccount, compress, decompress
from driftpy.user_map.polling_sub import PollingSubscription
from driftpy.user_map.types import UserMapInterface
from driftpy.user_map.user_map_config import PollingConfig, UserMapConfig
from driftpy.user_map.websocket_sub import WebsocketSubscription


class UserMap(UserMapInterface, DLOBSource):
    def __init__(self, config: UserMapConfig):
        self.user_map: Dict[str, DriftUser] = {}
        self.raw: Dict[str, bytes] = {}
        self.last_number_of_sub_accounts = None
        self.sync_lock = asyncio.Lock()
        self.drift_client: DriftClient = config.drift_client
        self.latest_slot: int = 0
        self.is_subscribed = False
        self.last_dumped_slot = 0
        if config.connection:
            self.connection = config.connection
        else:
            self.connection = self.drift_client.connection
        self.commitment = config.subscription_config.commitment or Confirmed
        self.include_idle = config.include_idle or False
        if isinstance(config.subscription_config, PollingConfig):
            self.subscription = PollingSubscription(
                self, config.subscription_config.frequency, config.skip_initial_load
            )
        else:
            self.subscription = WebsocketSubscription(
                self,
                self.commitment,
                self.update_user_account,
                config.skip_initial_load,
                config.subscription_config.resub_timeout_ms,
                decode=decode_user,
            )

    async def subscribe(self):
        if self.size() > 0:
            return

        await self.drift_client.subscribe()
        self.last_number_of_sub_accounts = (
            self.drift_client.get_state_account().max_number_of_sub_accounts
        )
        # there is no event emitter yet
        # if there was, we'd subscribe to it here as well
        await self.subscription.subscribe()
        self.is_subscribed = True

    async def unsubscribe(self) -> None:
        await self.subscription.unsubscribe()

        for key in list(self.user_map.keys()):
            user = self.user_map[key]
            try:
                await user.unsubscribe()
            except TypeError:
                # Handle cases where unsubscribe is not async (e.g., Polling)
                user.unsubscribe()
            finally:
                del self.user_map[key]

        if self.last_number_of_sub_accounts:
            # again, no event emitter
            self.last_number_of_sub_accounts = None

        self.is_subscribed = False

    def has(self, key: str) -> bool:
        return key in self.user_map

    def get(self, key: str) -> Optional[DriftUser]:
        return self.user_map.get(key)

    def size(self) -> int:
        return len(self.user_map)

    def values(self):
        return iter(self.user_map.values())

    def clear(self):
        self.user_map.clear()

    def get_user_authority(self, user_account_public_key: str) -> Optional[Pubkey]:
        user = self.user_map.get(user_account_public_key)
        if not user:
            return None
        return user.get_user_account().authority

    async def must_get(self, key: str) -> DriftUser:
        if not self.has(key):
            pubkey = Pubkey.from_string(key)
            await self.add_pubkey(pubkey)
        return self.get(key)

    async def add_pubkey(
        self,
        user_account_public_key: Pubkey,
        data: Optional[DataAndSlot[UserAccount]] = None,
    ) -> None:
        user = DriftUser(
            self.drift_client,
            user_public_key=user_account_public_key,
            account_subscription=AccountSubscriptionConfig(
                "cached", commitment=self.commitment
            ),
        )

        if data is not None:
            user.account_subscriber.update_data(data)
        else:
            await user.subscribe()

        self.user_map[str(user_account_public_key)] = user

    async def update_with_order_record(self, record: OrderRecord):
        self.must_get(str(record.user))

    async def sync(self) -> None:
        async with self.sync_lock:
            try:
                filters = [{"memcmp": {"offset": 0, "bytes": "TfwwBiNJtao"}}]
                if not self.include_idle:
                    filters.append({"memcmp": {"offset": 4350, "bytes": "1"}})

                rpc_request = jsonrpcclient.request(
                    "getProgramAccounts",
                    (
                        str(self.drift_client.program_id),
                        {"filters": filters, "encoding": "base64", "withContext": True},
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
                    raise ValueError(f"Error fetching user map: {parsed_resp.message}")

                if not isinstance(parsed_resp, jsonrpcclient.Ok):
                    raise ValueError(f"Error fetching user map - not ok: {parsed_resp}")

                slot = int(parsed_resp.result["context"]["slot"])

                self.latest_slot = slot

                rpc_response_values = parsed_resp.result["value"]

                program_account_buffer_map: Dict[str, Container[Any]] = {}
                raw: Dict[str, bytes] = {}

                # parse the gPA data before inserting
                for program_account in rpc_response_values:
                    pubkey = program_account["pubkey"]
                    raw_bytes = base64.b64decode(program_account["account"]["data"][0])
                    data = decode_user(raw_bytes)
                    program_account_buffer_map[str(pubkey)] = data
                    raw[str(pubkey)] = raw_bytes

                self.raw = raw

                # "idempotent" insert into usermap
                for pubkey in program_account_buffer_map.keys():
                    data = program_account_buffer_map.get(pubkey)
                    user_account: UserAccount = data
                    if pubkey not in self.user_map:
                        await self.add_pubkey(
                            Pubkey.from_string(pubkey), DataAndSlot(slot, user_account)
                        )
                        self.user_map.get(pubkey).account_subscriber.update_data(
                            DataAndSlot(slot, user_account)
                        )
                    else:
                        self.user_map.get(pubkey).account_subscriber.update_data(
                            DataAndSlot(slot, user_account)
                        )
                    # let the loop breathe
                    await asyncio.sleep(0)

                # remove any stale data from the usermap or update the data to the latest gPA data
                keys_to_delete = []
                for key in list(self.user_map.keys()):
                    if key not in program_account_buffer_map:
                        self.user_map[key].unsubscribe()
                        keys_to_delete.append(key)
                    await asyncio.sleep(0)

                for key in keys_to_delete:
                    del self.user_map[key]

            except Exception as e:
                print(f"Error in UserMap.sync(): {e}")

    # this is used as a callback for ws subscriptions to update data as its streamed
    async def update_user_account(self, key: str, data: DataAndSlot[UserAccount]):
        user: DriftUser = await self.must_get(key)
        user.account_subscriber.update_data(data)

    async def get_DLOB(self, slot: int):
        from driftpy.dlob.dlob import DLOB

        dlob = DLOB()
        dlob.init_from_usermap(self, slot)
        return dlob

    def get_slot(self) -> int:
        return self.latest_slot

    def get_last_dump_filepath(self) -> str:
        return f"usermap_{self.last_dumped_slot}.pkl"

    async def load(self, filename: Optional[str] = None):
        if not filename:
            filename = self.get_last_dump_filepath()
        if not os.path.exists(filename):
            raise FileNotFoundError(f"File {filename} not found")
        start = filename.index("_") + 1
        end = filename.index(".")
        slot = int(filename[start:end])
        with open(filename, "rb") as f:
            users: list[PickledData] = pickle.load(f)
            for user in users:
                decompressed_data = decompress(user.data)
                data = decode_user(decompressed_data)
                await self.add_pubkey(user.pubkey, DataAndSlot(slot, data))

    def dump(self, filename: Optional[str] = None):
        users = []
        for pubkey, user in self.raw.items():
            users.append(PickledData(pubkey=pubkey, data=compress(user)))
        self.last_dumped_slot = self.get_slot()
        path = filename or f"usermap_{self.last_dumped_slot}.pkl"
        with open(path, "wb") as f:
            pickle.dump(users, f, pickle.HIGHEST_PROTOCOL)
