from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Literal, Union, Optional

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solders.pubkey import Pubkey

from driftpy.constants.config import DRIFT_PROGRAM_ID
from driftpy.events.grpc_log_provider import GrpcLogProvider
from driftpy.types import (
    CurveRecord,
    DepositRecord,
    FundingPaymentRecord,
    FundingRateRecord,
    GrpcLogProviderConfig,
    InsuranceFundRecord,
    InsuranceFundStakeRecord,
    LiquidationRecord,
    LogProviderCallback,
    LPRecord,
    NewUserRecord,
    OrderActionRecord,
    OrderRecord,
    SettlePnlRecord,
    SpotInterestRecord,
    SwapRecord,
)

EventType = Literal[
    "NewUserRecord",
    "DepositRecord",
    "SpotInterestRecord",
    "CurveRecord",
    "InsuranceFundRecord",
    "InsuranceFundStakeRecord",
    "LPRecord",
    "FundingRateRecord",
    "FundingPaymentRecord",
    "LiquidationRecord",
    "SettlePnlRecord",
    "OrderRecord",
    "OrderActionRecord",
    "SwapRecord",
    "SpotMarketVaultDepositRecord",
    "SignedMsgOrderRecord",
    "DeleteUserRecord",
    "FuelSweepRecord",
    "FuelSeasonRecord",
]

Event = Union[
    NewUserRecord,
    DepositRecord,
    SpotInterestRecord,
    CurveRecord,
    InsuranceFundRecord,
    InsuranceFundStakeRecord,
    LPRecord,
    FundingRateRecord,
    FundingPaymentRecord,
    LiquidationRecord,
    SettlePnlRecord,
    OrderRecord,
    OrderActionRecord,
    SwapRecord,
]


@dataclass
class WrappedEvent:
    event_type: EventType
    tx_sig: any
    slot: int
    tx_sig_index: int
    data: Event


SortFn = Callable[[WrappedEvent, WrappedEvent], int]

EventSubscriptionOrderBy = Literal["blockchain", "client"]
Asc = Literal["asc"]
Desc = Literal["desc"]
EventSubscriptionOrderDirection = Union[Asc, Desc]


@dataclass
class WebsocketLogProviderConfig:
    pass


@dataclass
class PollingLogProviderConfig:
    frequency: float = 1
    batch_size: Optional[int] = None


LogProviderConfig = Union[
    WebsocketLogProviderConfig, PollingLogProviderConfig, GrpcLogProviderConfig
]


class LogProvider:
    @abstractmethod
    def is_subscribed(self):
        pass

    @abstractmethod
    def subscribe(
        self,
        callback: LogProviderCallback,
    ) -> bool:
        pass

    @abstractmethod
    def unsubscribe(self):
        pass


DEFAULT_EVENT_TYPES = (
    "NewUserRecord",
    "DepositRecord",
    "SpotInterestRecord",
    "CurveRecord",
    "InsuranceFundRecord",
    "InsuranceFundStakeRecord",
    "LPRecord",
    "FundingRateRecord",
    "FundingPaymentRecord",
    "LiquidationRecord",
    "SettlePnlRecord",
    "OrderRecord",
    "OrderActionRecord",
    "SwapRecord",
    "SpotMarketVaultDepositRecord",
    "SignedMsgOrderRecord",
    "DeleteUserRecord",
    "FuelSweepRecord",
    "FuelSeasonRecord",
)


@dataclass
class EventSubscriptionOptions:
    address: Pubkey = DRIFT_PROGRAM_ID
    event_types: tuple[EventType] = DEFAULT_EVENT_TYPES
    max_events_per_type: int = 4096
    order_by: EventSubscriptionOrderBy = "blockchain"
    order_dir: EventSubscriptionOrderDirection = "asc"
    commitment: Commitment = "confirmed"
    max_tx: int = 4096
    log_provider_config: LogProviderConfig = field(
        default_factory=WebsocketLogProviderConfig
    )
    until_tx: any = None

    @staticmethod
    def default():
        return EventSubscriptionOptions()

    def get_log_provider(self, connection: AsyncClient):
        if isinstance(self.log_provider_config, WebsocketLogProviderConfig):
            from driftpy.events.websocket_log_provider import WebsocketLogProvider

            return WebsocketLogProvider(connection, self.address, self.commitment)

        elif isinstance(self.log_provider_config, GrpcLogProviderConfig):
            return GrpcLogProvider(
                self.log_provider_config,
                commitment=self.commitment,
                user_account_to_filter=self.user_account_to_filter,
            )

        else:
            if (
                str(self.commitment) != "confirmed"
                and str(self.commitment) != "finalized"
            ):
                raise ValueError(
                    f"PollingLogProvider does not support commitment {self.commitment}"
                )

            from driftpy.events.polling_log_provider import PollingLogProvider

            return PollingLogProvider(
                connection,
                self.address,
                self.commitment,
                self.log_provider_config.frequency,
                self.log_provider_config.batch_size,
            )
