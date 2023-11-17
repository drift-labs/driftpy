from abc import abstractmethod
from dataclasses import dataclass
from typing import TypeVar, Generic, Optional

from solders.pubkey import Pubkey

from driftpy.types import (
    PerpMarket,
    SpotMarket,
    OracleSource,
    User,
    OraclePriceData,
    State,
)

T = TypeVar("T")


@dataclass
class DataAndSlot(Generic[T]):
    slot: int
    data: T


class DriftClientAccountSubscriber:
    @abstractmethod
    async def get_state_account_and_slot(self) -> Optional[DataAndSlot[State]]:
        pass

    @abstractmethod
    async def get_perp_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[PerpMarket]]:
        pass

    @abstractmethod
    async def get_spot_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[SpotMarket]]:
        pass

    @abstractmethod
    async def get_oracle_data_and_slot(
        self, oracle: Pubkey
    ) -> Optional[DataAndSlot[OraclePriceData]]:
        pass


class UserAccountSubscriber:
    @abstractmethod
    async def get_user_account_and_slot(self) -> Optional[DataAndSlot[User]]:
        pass
