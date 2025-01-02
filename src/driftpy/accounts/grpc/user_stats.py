from typing import Optional

from driftpy.accounts.grpc.account_subscriber import GrpcAccountSubscriber
from driftpy.accounts.types import DataAndSlot, UserStatsAccountSubscriber
from driftpy.types import UserStatsAccount


class GrpcUserStatsAccountSubscriber(
    GrpcAccountSubscriber[UserStatsAccount], UserStatsAccountSubscriber
):
    def get_user_stats_account_and_slot(
        self,
    ) -> Optional[DataAndSlot[UserStatsAccount]]:
        return self.data_and_slot
