from typing import Optional
from driftpy.drift_client import DriftClient
from driftpy.types import UserAccount
from solders.pubkey import Pubkey
from solana.rpc.types import TxOpts
from abc import ABC, abstractmethod

class AuctionSubscriberConfig:
    def __init__(self, drift_client: DriftClient, opts: Optional[TxOpts], resub_timeout_ms: Optional[int]):
        self.drift_client = drift_client
        self.opts = opts
        self.resub_timeout_ms = resub_timeout_ms

class AuctionSubscriberEvents(ABC):
    @abstractmethod
    def on_account_update(self, account: UserAccount, pubkey: Pubkey, slot: int) -> None:
        """
        Abstract method to handle account updates.

        :param account: UserAccount instance.
        :param pubkey: PublicKey instance.
        :param slot: Slot number as an integer.
        """
        pass
