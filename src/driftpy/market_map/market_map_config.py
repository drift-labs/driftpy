from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from dataclasses import dataclass
from typing import Optional, Union
from driftpy.drift_client import DriftClient
from driftpy.types import MarketType


@dataclass
class WebsocketConfig:
    resub_timeout_ms: Optional[int] = None
    commitment: Optional[Commitment] = None


@dataclass
class MarketMapConfig:
    drift_client: DriftClient
    market_type: MarketType  # perp market map or spot market map
    subscription_config: WebsocketConfig
    connection: Optional[AsyncClient] = None
    skip_initial_load: Optional[bool] = None
