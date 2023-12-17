from driftpy.dlob.dlob import DLOB
from driftpy.drift_client import DriftClient
from abc import ABC, abstractmethod

class DLOBSource(ABC):
    @abstractmethod
    async def getDLOB(self, slot: int):
        pass

class SlotSource(ABC):
    @abstractmethod
    def get_slot(self) -> int:
        pass

class DLOBSubscriptionConfig:
    def __init__(self, drift_client: DriftClient, dlob_source: DLOBSource, slot_source: SlotSource, update_frequency: int):
        self.drift_client = drift_client
        self.dlob_source = dlob_source
        self.slot_source = slot_source
        self.update_frequency = update_frequency

class DLOBSubscriberEvents(ABC):

    @abstractmethod
    def update(self, dlob: DLOB) -> None:
        pass

    @abstractmethod
    def error(self, e: Exception) -> None:
        pass
