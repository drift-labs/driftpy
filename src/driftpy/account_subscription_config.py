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
from driftpy.accounts.demo import (
    DemoDriftClientAccountSubscriber,
    DemoUserAccountSubscriber,
)
from driftpy.types import OracleInfo


class AccountSubscriptionConfig:
    @staticmethod
    def default():
        return AccountSubscriptionConfig("websocket")

    def __init__(
        self,
        type: Literal["polling", "websocket", "cached", "demo"],
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

    def get_drift_client_subscriber(
        self,
        program: Program,
        perp_market_indexes: list[int] = None,
        spot_market_indexes: list[int] = None,
        oracle_infos: list[OracleInfo] = None,
    ):
        should_find_all_markets_and_oracles = (
            perp_market_indexes is None
            and spot_market_indexes is None
            and oracle_infos is None
        )
        perp_market_indexes = [] if perp_market_indexes is None else perp_market_indexes
        spot_market_indexes = [] if spot_market_indexes is None else spot_market_indexes
        oracle_infos = [] if oracle_infos is None else oracle_infos

        match self.type:
            case "polling":
                return PollingDriftClientAccountSubscriber(
                    program,
                    self.bulk_account_loader,
                    perp_market_indexes,
                    spot_market_indexes,
                    oracle_infos,
                    should_find_all_markets_and_oracles,
                )
            case "websocket":
                return WebsocketDriftClientAccountSubscriber(
                    program,
                    perp_market_indexes,
                    spot_market_indexes,
                    oracle_infos,
                    should_find_all_markets_and_oracles,
                    self.commitment,
                )
            case "cached":
                return CachedDriftClientAccountSubscriber(
                    program,
                    perp_market_indexes,
                    spot_market_indexes,
                    oracle_infos,
                    should_find_all_markets_and_oracles,
                    self.commitment,
                )
            case "demo":
                if (
                    perp_market_indexes == []
                    or spot_market_indexes == []
                    or oracle_infos == []
                ):
                    raise ValueError(
                        "spot_market_indexes / perp_market_indexes / oracle_infos all must be provided with demo config"
                    )
                return DemoDriftClientAccountSubscriber(
                    program,
                    perp_market_indexes,
                    spot_market_indexes,
                    oracle_infos,
                    self.commitment,
                )

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
            case "demo":
                return DemoUserAccountSubscriber(user_pubkey, program, self.commitment)
