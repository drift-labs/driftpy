from typing import Optional
from driftpy.drift_client import DriftClient
from solana.rpc.types import Commitment

class AuctionSubscriberConfig:
    def __init__(
            self, 
            drift_client: DriftClient, 
            commitment: Optional[Commitment] = None, 
            resub_timeout_ms: Optional[int] = None
        ):
        self.drift_client = drift_client
        self.commitment = commitment
        self.resub_timeout_ms = resub_timeout_ms

