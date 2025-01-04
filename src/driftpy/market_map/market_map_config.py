from dataclasses import dataclass
from typing import Optional

from anchorpy import Program
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment

from driftpy.types import GrpcConfig, MarketType


@dataclass
class WebsocketConfig:
    resub_timeout_ms: Optional[int] = None
    commitment: Optional[Commitment] = None


@dataclass
class MarketMapConfig:
    program: Program
    market_type: MarketType  # perp market map or spot market map
    subscription_config: WebsocketConfig
    connection: AsyncClient


@dataclass
class GrpcMarketMapConfig:
    program: Program
    market_type: MarketType  # perp market map or spot market map
    grpc_config: GrpcConfig
    connection: AsyncClient
