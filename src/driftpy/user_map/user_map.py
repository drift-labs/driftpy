import asyncio
import traceback
from typing import Optional, Dict
from asyncio import Future

from solders.pubkey import Pubkey

from solana.rpc.commitment import Confirmed

from driftpy.accounts.bulk_account_loader import BulkAccountLoader
from driftpy.drift_user import DriftUser
from driftpy.account_subscription_config import AccountSubscriptionConfig

from driftpy.types import StateAccount, UserAccount

from driftpy.user_map.user_map_config import UserMapConfig, PollingConfig
from driftpy.user_map.websocket_sub import WebsocketSubscription
from driftpy.user_map.polling_sub import PollingSubscription

from driftpy.memcmp import get_user_filter, get_non_idle_user_filter

from driftpy.user_map.types import UserMapInterface, ConfigType
from driftpy.accounts.types import DataAndSlot

class UserMap(UserMapInterface):
    def __init__(self, config: UserMapConfig):
        self.user_map: Dict[str, DriftUser] = {}
        self.last_number_of_sub_accounts = None
        self.sync_promise = None
        self.sync_promise_resolver = None
        self.drift_client = config.drift_client
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
            self.subscription = WebsocketSubscription(self, self.commitment, self.update_user_account, config.subscription_config.resub_timeout_ms, config.skip_initial_load)

    async def state_account_update_callback(self, state: StateAccount):
        if state.max_number_of_sub_accounts != self.last_number_of_sub_accounts:
            await self.sync()
            self.last_number_of_sub_accounts = state.max_number_of_sub_accounts

    async def subscribe(self):
        if self.size() > 0:
            return
        
        await self.drift_client.subscribe()
        self.last_number_of_sub_accounts = self.drift_client.get_state_account().max_number_of_sub_accounts
        # There is no event emitter yet
        await self.subscription.subscribe()
        self.is_subscribed = True

    async def unsubscribe(self) -> None:
        await self.subscription.unsubscribe()

        for key in list(self.user_map.keys()):
            user = self.user_map[key]
            user.unsubscribe()
            del self.user_map[key]
        
        if self.last_number_of_sub_accounts:
            # Again, no event emitter
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
    
    def get_user_authority(self, key: str) -> Optional[Pubkey]:
        ch_user = self.user_map.get(key)
        if not ch_user:
            return None
        return ch_user.get_user_account().authority
    
    async def must_get(self, key: str) -> DriftUser:
        if not self.has(key):
            pubkey = Pubkey.from_string(key)
            await self.add_pubkey(pubkey)
        return self.get(key)
    
    async def add_pubkey(
            self, 
            user_account_public_key: Pubkey, 
        ) -> None:
        if isinstance(self.subscription, PollingSubscription):
            bulk_account_loader = BulkAccountLoader(self.drift_client.connection)
            config = AccountSubscriptionConfig(ConfigType.POLLING.value, bulk_account_loader, self.commitment)
        elif isinstance(self.subscription, WebsocketSubscription):
            config = AccountSubscriptionConfig(ConfigType.WEBSOCKET.value, commitment = self.commitment)
        else:
            config = AccountSubscriptionConfig(ConfigType.CACHED.value)
        user = DriftUser(
            self.drift_client, 
            authority = user_account_public_key,
            account_subscription = config
            )
        await user.subscribe()
        self.user_map[str(user_account_public_key)] = user

    async def sync(self):
        if self.sync_promise:
            return self.sync_promise

        self.sync_promise = Future()

        try:
            filters = (get_user_filter(),)
            if not self.include_idle:
                filters += (get_non_idle_user_filter(),)

            rpc_json_response = await self.connection.get_program_accounts(self.drift_client.program_id, self.commitment, 'base64', filters=filters)
            rpc_response_and_context = rpc_json_response.value

            slot = (await self.drift_client.program.provider.connection.get_slot()).value
            program_account_buffer_map = {}

            for program_account in rpc_response_and_context:
                pubkey = program_account.pubkey
                data = program_account.account.data
                program_account_buffer_map[str(pubkey)] = data

            for key, buffer in program_account_buffer_map.items():
                if key not in self.user_map:
                    data = program_account_buffer_map.get(key)
                    user_account = self.drift_client.program.coder.accounts.decode(data)
                    await self.add_pubkey(Pubkey.from_string(key))
                await asyncio.sleep(0)

            for key, user in self.user_map.items():
                if key not in program_account_buffer_map:
                    user.unsubscribe()
                    del self.user_map[key]
                else:
                    user_account = self.drift_client.program.coder.accounts.decode(program_account_buffer_map.get(key))
                    user.account_subscriber._update_data(DataAndSlot(slot, user_account))
                await asyncio.sleep(0)

        except Exception as e:
            print(f"Error in UserMap.sync(): {e}")
            traceback.print_exc()

        finally:
            if self.sync_promise_resolver:
                self.sync_promise_resolver()
            self.sync_promise = None

    async def update_user_account(self, key: str, data: DataAndSlot[UserAccount]):
        user: DriftUser = await self.must_get(key)
        user.account_subscriber._update_data(data)