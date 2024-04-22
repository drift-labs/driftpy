import asyncio

from typing import Optional

from driftpy.accounts import DataAndSlot
from driftpy.types import UserAccount

from driftpy.accounts.ws.account_subscriber import WebsocketAccountSubscriber
from driftpy.accounts.types import UserAccountSubscriber


class WebsocketUserAccountSubscriber(
    WebsocketAccountSubscriber[UserAccount], UserAccountSubscriber
):
    def get_user_account_and_slot(self) -> Optional[DataAndSlot[UserAccount]]:
        data_and_slot = self.data_and_slot
        while data_and_slot is None:
            asyncio.create_task(self.fetch())
            data_and_slot = self.data_and_slot
        return data_and_slot
