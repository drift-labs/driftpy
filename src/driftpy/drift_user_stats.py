from dataclasses import dataclass
from typing import Optional

from solders.pubkey import Pubkey
from solana.rpc.commitment import Commitment, Confirmed

from driftpy.accounts.types import DataAndSlot
from driftpy.types import ReferrerInfo, UserStatsAccount
from driftpy.accounts.ws.user_stats import WebsocketUserStatsAccountSubscriber
from driftpy.addresses import (
    get_user_account_public_key,
    get_user_stats_account_public_key,
)


@dataclass
class UserStatsSubscriptionConfig:
    commitment: Commitment = Confirmed
    resub_timeout_ms: Optional[int] = None
    initial_data: Optional[DataAndSlot[UserStatsAccount]] = None


class DriftUserStats:
    def __init__(
        self,
        drift_client,
        user_stats_account_pubkey: Pubkey,
        config: UserStatsSubscriptionConfig,
    ):
        self.drift_client = drift_client
        self.user_stats_account_pubkey = user_stats_account_pubkey
        self.account_subscriber = WebsocketUserStatsAccountSubscriber(
            user_stats_account_pubkey,
            drift_client.program,
            config.commitment,
            initial_data=config.initial_data,
        )
        self.subscribed = False

    async def subscribe(self) -> bool:
        if self.subscribed:
            return

        await self.account_subscriber.subscribe()
        self.subscribed = True

        return self.subscribed

    async def fetch_accounts(self):
        await self.account_subscriber.fetch()

    def unsubscribe(self):
        self.account_subscriber.unsubscribe()

    def get_account_and_slot(self) -> DataAndSlot[UserStatsAccount]:
        return self.account_subscriber.get_user_stats_account_and_slot()

    def get_account(self) -> UserStatsAccount:
        return self.account_subscriber.get_user_stats_account_and_slot().data

    def get_referrer_info(self) -> Optional[ReferrerInfo]:
        if self.get_account().referrer == Pubkey.default():
            return None
        else:
            return ReferrerInfo(
                get_user_account_public_key(
                    self.drift_client.program_id, self.get_account().referrer, 0
                ),
                get_user_stats_account_public_key(
                    self.drift_client.program_id, self.get_account().referrer
                ),
            )
