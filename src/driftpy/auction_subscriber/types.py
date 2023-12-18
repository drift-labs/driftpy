from typing import Optional
from driftpy.drift_client import DriftClient
from solana.rpc.types import TxOpts

class AuctionSubscriberConfig:
    def __init__(self, drift_client: DriftClient, opts: Optional[TxOpts], resub_timeout_ms: Optional[int]):
        self.drift_client = drift_client
        self.opts = opts
        self.resub_timeout_ms = resub_timeout_ms

