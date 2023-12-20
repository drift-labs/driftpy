from abc import abstractmethod
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar, Generic, Optional, Sequence
from solana.rpc.types import MemcmpOpts
from solana.rpc.commitment import Commitment
from solders.pubkey import Pubkey

from driftpy.types import (
    PerpMarketAccount,
    SpotMarketAccount,
    OracleSource,
    UserAccount,
    OraclePriceData,
    StateAccount,
)

T = TypeVar("T")


@dataclass
class DataAndSlot(Generic[T]):
    slot: int
    data: T

@dataclass
class BufferAndSlot:
    slot: int
    buffer: bytes

@dataclass
class WebsocketProgramAccountOptions:
    filters: Sequence[MemcmpOpts]
    commitment: Commitment
    encoding: str

UpdateCallback = Callable[[str, DataAndSlot[UserAccount]], Awaitable[None]]

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
