from typing import Optional

from driftpy.accounts.grpc.account_subscriber import GrpcAccountSubscriber
from driftpy.accounts.types import DataAndSlot, UserAccountSubscriber
from driftpy.types import UserAccount


class GrpcUserAccountSubscriber(
    GrpcAccountSubscriber[UserAccount], UserAccountSubscriber
):
    def get_user_account_and_slot(self) -> Optional[DataAndSlot[UserAccount]]:
        return self.data_and_slot
