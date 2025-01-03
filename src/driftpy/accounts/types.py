from abc import abstractmethod
from dataclasses import dataclass
from typing import Awaitable, Callable, Generic, Optional, Sequence, TypeVar, Union

from solana.rpc.commitment import Commitment
from solana.rpc.types import MemcmpOpts
from solders.pubkey import Pubkey

from driftpy.types import (
    OraclePriceData,
    OracleSource,
    PerpMarketAccount,
    SpotMarketAccount,
    StateAccount,
    UserAccount,
    UserStatsAccount,
)

T = TypeVar("T")


@dataclass
class DataAndSlot(Generic[T]):
    slot: int
    data: T


@dataclass
class FullOracleWrapper:
    pubkey: Pubkey
    oracle_source: OracleSource
    oracle_price_data_and_slot: Optional[DataAndSlot[OraclePriceData]]


@dataclass
class BufferAndSlot:
    slot: int
    buffer: bytes


@dataclass
class WebsocketProgramAccountOptions:
    filters: Sequence[MemcmpOpts]
    commitment: Commitment
    encoding: str


@dataclass
class GrpcProgramAccountOptions:
    filters: Sequence[MemcmpOpts]
    commitment: Commitment


UpdateCallback = Callable[[str, DataAndSlot[UserAccount]], Awaitable[None]]

MarketUpdateCallback = Callable[
    [str, DataAndSlot[Union[PerpMarketAccount, SpotMarketAccount]]], Awaitable[None]
]


class DriftClientAccountSubscriber:
    @abstractmethod
    async def subscribe(self):
        pass

    @abstractmethod
    def unsubscribe(self):
        pass

    @abstractmethod
    async def fetch(self):
        pass

    @abstractmethod
    def get_state_account_and_slot(self) -> Optional[DataAndSlot[StateAccount]]:
        pass

    @abstractmethod
    def get_perp_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[PerpMarketAccount]]:
        pass

    @abstractmethod
    def get_spot_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[SpotMarketAccount]]:
        pass

    @abstractmethod
    def get_oracle_price_data_and_slot(
        self, oracle: Pubkey
    ) -> Optional[DataAndSlot[OraclePriceData]]:
        pass

    @abstractmethod
    def get_market_accounts_and_slots(self) -> list[DataAndSlot[PerpMarketAccount]]:
        pass

    @abstractmethod
    def get_spot_market_accounts_and_slots(
        self,
    ) -> list[DataAndSlot[SpotMarketAccount]]:
        pass


class UserAccountSubscriber:
    @abstractmethod
    async def subscribe(self):
        pass

    @abstractmethod
    def unsubscribe(self):
        pass

    @abstractmethod
    async def fetch(self):
        pass

    async def update_data(self, data: Optional[DataAndSlot[UserAccount]]):
        pass

    @abstractmethod
    def get_user_account_and_slot(self) -> Optional[DataAndSlot[UserAccount]]:
        pass


class UserStatsAccountSubscriber:
    @abstractmethod
    async def subscribe(self):
        pass

    @abstractmethod
    def unsubscribe(self):
        pass

    @abstractmethod
    async def fetch(self):
        pass

    @abstractmethod
    def get_user_stats_account_and_slot(
        self,
    ) -> Optional[DataAndSlot[UserStatsAccount]]:
        pass
