from typing import Optional

from driftpy.accounts import DataAndSlot
from driftpy.accounts.types import UserStatsAccountSubscriber
from driftpy.accounts.ws.account_subscriber import WebsocketAccountSubscriber
from driftpy.types import UserStatsAccount


class WebsocketUserStatsAccountSubscriber(
    WebsocketAccountSubscriber[UserStatsAccount], UserStatsAccountSubscriber
):
    def get_user_stats_account_and_slot(
        self,
    ) -> Optional[DataAndSlot[UserStatsAccount]]:
        return self.data_and_slot
