from typing import Literal, Optional

from solders.pubkey import Pubkey

from driftpy.accounts.bulk_account_loader import BulkAccountLoader
from driftpy.accounts.cache import (
    CachedDriftClientAccountSubscriber,
    CachedUserAccountSubscriber,
)
from driftpy.accounts.polling import (
    PollingDriftClientAccountSubscriber,
    PollingUserAccountSubscriber,
)
from anchorpy import Program

from driftpy.accounts.ws import (
    WebsocketDriftClientAccountSubscriber,
    WebsocketUserAccountSubscriber,
)


class AccountSubscriptionConfig:
    @staticmethod
    def default():
        return AccountSubscriptionConfig("websocket")

    def __init__(
        self,
        type: Literal["polling", "websocket", "cached"],
        bulk_account_loader: Optional[BulkAccountLoader] = None,
    ):
        self.type = type

        if self.type == "polling":
            if bulk_account_loader is None:
                raise ValueError("polling subscription requires bulk account loader")

            self.bulk_account_loader = bulk_account_loader

    def get_drift_client_subscriber(self, program: Program):
        match self.type:
            case "polling":
                return PollingDriftClientAccountSubscriber(
                    program, self.bulk_account_loader
                )
            case "websocket":
                return WebsocketDriftClientAccountSubscriber(program)
            case "cached":
                return CachedDriftClientAccountSubscriber(program)

    def get_user_client_subscriber(self, program: Program, user_pubkey: Pubkey):
        match self.type:
            case "polling":
                return PollingUserAccountSubscriber(
                    user_pubkey, program, self.bulk_account_loader
                )
            case "websocket":
                return WebsocketUserAccountSubscriber(user_pubkey, program)
            case "cached":
                return CachedUserAccountSubscriber(user_pubkey, program)
