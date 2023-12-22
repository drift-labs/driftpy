from abc import ABC, abstractmethod
from dataclasses import dataclass

from driftpy.dlob.dlob import DLOB
from driftpy.drift_client import DriftClient


class DLOBSource(ABC):
    @abstractmethod
    async def get_DLOB(self, slot: int) -> DLOB:
        pass


class SlotSource(ABC):
    @abstractmethod
    def get_slot(self) -> int:
        pass


@dataclass
class DLOBClientConfig:
    drift_client: DriftClient
    dlob_source: DLOBSource
    slot_source: SlotSource
    update_frequency: int
