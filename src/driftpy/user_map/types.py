from abc import ABC, abstractmethod
from driftpy.drift_user import DriftUser
from solders.pubkey import Pubkey
from typing import Optional

class UserMapInterface(ABC):

    @abstractmethod
    async def subscribe(self) -> None:
        pass

    @abstractmethod
    async def unsubscribe(self) -> None:
        pass

    @abstractmethod
    async def add_pubkey(self, user_account_public_key: Pubkey) -> None:
        pass

    @abstractmethod
    def has(self, key: str) -> bool:
        pass

    @abstractmethod
    def get(self, key: str) -> Optional[DriftUser]:
        pass

    @abstractmethod
    def must_get(self, key: str) -> DriftUser:
        pass

    @abstractmethod
    def get_user_authority(self, key: str) -> Optional[Pubkey]:
        pass

    @abstractmethod
    def values(self):
        pass