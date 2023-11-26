from typing import Literal, Optional

from solders.pubkey import Pubkey
from solana.rpc.commitment import Commitment

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
        commitment: Commitment = None,
    ):
        self.type = type

        if self.type == "polling":
            if bulk_account_loader is None:
                raise ValueError("polling subscription requires bulk account loader")

            if commitment is not None and commitment != bulk_account_loader.commitment:
                raise ValueError(
                    f"bulk account loader commitment {bulk_account_loader.commitment} != commitment passed {commitment}"
                )

            self.bulk_account_loader = bulk_account_loader

        self.commitment = commitment

    def get_drift_client_subscriber(self, program: Program):
        match self.type:
            case "polling":
                return PollingDriftClientAccountSubscriber(
                    program, self.bulk_account_loader
                )
            case "websocket":
                return WebsocketDriftClientAccountSubscriber(program, self.commitment)
            case "cached":
                return CachedDriftClientAccountSubscriber(program, self.commitment)

    def get_user_client_subscriber(self, program: Program, user_pubkey: Pubkey):
        match self.type:
            case "polling":
                return PollingUserAccountSubscriber(
                    user_pubkey, program, self.bulk_account_loader
                )
            case "websocket":
                return WebsocketUserAccountSubscriber(
                    user_pubkey, program, self.commitment
                )
            case "cached":
                return CachedUserAccountSubscriber(
                    user_pubkey, program, self.commitment
                )
