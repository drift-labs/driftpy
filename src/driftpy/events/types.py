from dataclasses import dataclass, field
from abc import abstractmethod
from solana.transaction import Signature
from solana.rpc.commitment import Commitment
from solana.rpc.async_api import AsyncClient

from typing import Callable, Literal, Union

from solders.pubkey import Pubkey

from driftpy.constants.config import DRIFT_PROGRAM_ID
from driftpy.types import (
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
# type: ignore
class WrappedEvent:
    event_type: EventType
    tx_sig: Signature
    slot: int
    tx_sig_index: int
    data: Event


SortFn = Callable[[WrappedEvent, WrappedEvent], int]

EventSubscriptionOrderBy = Union["blockchain", "client"]
Asc = Literal["asc"]
Desc = Literal["desc"]
EventSubscriptionOrderDirection = Union[Asc, Desc]


@dataclass
class WebsocketLogProviderConfig:
    pass


@dataclass
class PollingLogProviderConfig:
    frequency: float = 1
    batch_size: int = None


LogProviderConfig = Union[WebsocketLogProviderConfig, PollingLogProviderConfig]

LogProviderCallback = Callable[[Signature, int, list[str]], None]


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
    until_tx: Signature = None

    @staticmethod
    def default():
        return EventSubscriptionOptions()

    def get_log_provider(self, connection: AsyncClient):
        if isinstance(self.log_provider_config, WebsocketLogProviderConfig):
            from driftpy.events.websocket_log_provider import WebsocketLogProvider

            return WebsocketLogProvider(connection, self.address, self.commitment)
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
