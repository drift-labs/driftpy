from typing import Optional

from solana.rpc.commitment import Commitment

from driftpy.drift_client import DriftClient
from driftpy.types import GrpcConfig


class AuctionSubscriberConfig:
    def __init__(
        self,
        drift_client: DriftClient,
        commitment: Optional[Commitment] = None,
        resub_timeout_ms: Optional[int] = None,
    ):
        self.drift_client = drift_client
        self.commitment = commitment
        self.resub_timeout_ms = resub_timeout_ms


class GrpcAuctionSubscriberConfig(AuctionSubscriberConfig):
    def __init__(
        self,
        drift_client: DriftClient,
        grpc_config: GrpcConfig,
        commitment: Optional[Commitment] = None,
    ):
        super().__init__(drift_client, commitment)
        self.grpc_config = grpc_config
