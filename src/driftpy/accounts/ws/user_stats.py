from typing import Optional

from driftpy.accounts import DataAndSlot
from driftpy.types import UserStatsAccount

from driftpy.accounts.ws.account_subscriber import WebsocketAccountSubscriber
from driftpy.accounts.types import UserStatsAccountSubscriber


class WebsocketUserStatsAccountSubscriber(
    WebsocketAccountSubscriber[UserStatsAccount], UserStatsAccountSubscriber
):
    def get_user_stats_account_and_slot(
        self,
    ) -> Optional[DataAndSlot[UserStatsAccount]]:
        return self.data_and_slot
