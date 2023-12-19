import asyncio
import traceback
from typing import Any, Container, Optional, Dict

from solders.pubkey import Pubkey

from solana.rpc.commitment import Confirmed

from driftpy.accounts.bulk_account_loader import BulkAccountLoader
from driftpy.drift_client import DriftClient
from driftpy.drift_user import DriftUser
from driftpy.account_subscription_config import AccountSubscriptionConfig

from driftpy.types import StateAccount, UserAccount

from driftpy.user_map.user_map_config import UserMapConfig, PollingConfig
from driftpy.user_map.websocket_sub import WebsocketSubscription
from driftpy.user_map.polling_sub import PollingSubscription

from driftpy.memcmp import get_user_filter, get_non_idle_user_filter

from driftpy.user_map.types import UserMapInterface, ConfigType
from driftpy.accounts.types import DataAndSlot

from driftpy.decode.user import decode_user

class UserMap(UserMapInterface):
    def __init__(self, config: UserMapConfig):
        self.user_map: Dict[str, DriftUser] = {}
        self.last_number_of_sub_accounts = None
        self.sync_lock = asyncio.Lock()  
        self.sync_promise_resolver = None
        self.drift_client: DriftClient = config.drift_client
        self.is_subscribed = False
        if config.connection:
            self.connection = config.connection
        else:
            self.connection = self.drift_client.connection
        self.commitment = config.subscription_config.commitment or Confirmed
        self.include_idle = config.include_idle or False
        if isinstance(config.subscription_config, PollingConfig):
            self.subscription = PollingSubscription(self, config.subscription_config.frequency, config.skip_initial_load)
        else: 
            self.subscription = WebsocketSubscription(self, self.commitment, self.update_user_account, config.subscription_config.resub_timeout_ms, config.skip_initial_load, decode = decode_user)

    async def state_account_update_callback(self, state: StateAccount):
        if state.max_number_of_sub_accounts != self.last_number_of_sub_accounts:
            await self.sync()
            self.last_number_of_sub_accounts = state.max_number_of_sub_accounts

    async def subscribe(self):
        if self.size() > 0:
            return
        
        await self.drift_client.subscribe()
        self.last_number_of_sub_accounts = self.drift_client.get_state_account().max_number_of_sub_accounts
        # there is no event emitter yet
        # if there was, we'd subscribe to it here as well
        await self.subscription.subscribe()
        self.is_subscribed = True

    async def unsubscribe(self) -> None:
        await self.subscription.unsubscribe()

        for key in list(self.user_map.keys()):
            user = self.user_map[key]
            user.unsubscribe()
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
        ) -> None:
        config = self.subscription.get_subscription_config()
        user = DriftUser(
            self.drift_client, 
            authority = user_account_public_key,
            account_subscription = config
            )
        await user.subscribe()
        self.user_map[str(user_account_public_key)] = user

    async def sync(self) -> None:
        async with self.sync_lock:
            try:
                filters = (get_user_filter(),)
                if not self.include_idle:
                    filters += (get_non_idle_user_filter(),)

                rpc_json_response = await self.connection.get_program_accounts(self.drift_client.program_id, self.commitment, 'base64', filters=filters)
                rpc_response_and_context = rpc_json_response.value

                slot = (await self.drift_client.program.provider.connection.get_slot()).value
                program_account_buffer_map: Dict[str, Container[Any]] = {}

                # parse the gPA data before inserting
                for program_account in rpc_response_and_context:
                    pubkey = program_account.pubkey
                    data = decode_user(program_account.account.data)
                    program_account_buffer_map[str(pubkey)] = data

                # "idempotent" insert into usermap
                for key in program_account_buffer_map.keys():
                    if key not in self.user_map:
                        data = program_account_buffer_map.get(key)
                        user_account = data
                        await self.add_pubkey(Pubkey.from_string(key))
                        self.user_map.get(key).account_subscriber._update_data(DataAndSlot(slot, user_account))
                    # let the loop breathe
                    await asyncio.sleep(10)

                # remove any stale data from the usermap or update the data to the latest gPA data
                for key, user in self.user_map.items():
                    if key not in program_account_buffer_map:
                        user.unsubscribe()
                        del self.user_map[key]
                    # let the loop breathe
                    await asyncio.sleep(10)

            except Exception as e:
                print(f"Error in UserMap.sync(): {e}")
                traceback.print_exc()

    # this is used as a callback for ws subscriptions to update data as its streamed
    async def update_user_account(self, key: str, data: DataAndSlot[UserAccount]):
        user: DriftUser = await self.must_get(key)
        user.account_subscriber._update_data(data)