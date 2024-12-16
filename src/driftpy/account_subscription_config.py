from typing import Literal, Optional, cast

from anchorpy.program.core import Program
from solana.rpc.commitment import Commitment
from solders.pubkey import Pubkey

from driftpy.accounts.bulk_account_loader import BulkAccountLoader
from driftpy.accounts.cache import (
    CachedDriftClientAccountSubscriber,
    CachedUserAccountSubscriber,
)
from driftpy.accounts.demo import (
    DemoDriftClientAccountSubscriber,
    DemoUserAccountSubscriber,
)
from driftpy.accounts.polling import (
    PollingDriftClientAccountSubscriber,
    PollingUserAccountSubscriber,
)
from driftpy.accounts.types import FullOracleWrapper
from driftpy.accounts.ws import (
    WebsocketDriftClientAccountSubscriber,
    WebsocketUserAccountSubscriber,
)
from driftpy.types import OracleInfo


class AccountSubscriptionConfig:
    @staticmethod
    def default():
        return AccountSubscriptionConfig("websocket")

    def __init__(
        self,
        account_subscription_type: Literal["polling", "websocket", "cached", "demo"],
        bulk_account_loader: Optional[BulkAccountLoader] = None,
        commitment: Commitment = Commitment("confirmed"),
    ):
        self.type = account_subscription_type
        self.commitment = commitment
        self.bulk_account_loader = None

        if self.type != "polling":
            return

        if bulk_account_loader is None:
            raise ValueError("polling subscription requires bulk account loader")

        if commitment != bulk_account_loader.commitment:
            raise ValueError(
                f"bulk account loader commitment {bulk_account_loader.commitment} != commitment passed {commitment}"
            )

        self.bulk_account_loader = bulk_account_loader

    def get_drift_client_subscriber(
        self,
        program: Program,
        perp_market_indexes: list[int] | None = None,
        spot_market_indexes: list[int] | None = None,
        oracle_infos: list[OracleInfo] | None = None,
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
                if self.bulk_account_loader is None:
                    raise ValueError(
                        "polling subscription requires bulk account loader"
                    )
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
                    cast(list[FullOracleWrapper], oracle_infos),
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
                if self.bulk_account_loader is None:
                    raise ValueError(
                        "polling subscription requires bulk account loader"
                    )
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
