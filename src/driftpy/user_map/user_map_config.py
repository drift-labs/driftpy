from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from dataclasses import dataclass
from typing import Optional, Union
from driftpy.drift_client import DriftClient

@dataclass
class UserAccountFilterCriteria:
    # only return users that have open orders
    has_open_orders: bool

@dataclass
class PollingConfig:
    type: str
    frequency: int
    commitment: Optional[Commitment] = None

@dataclass
class WebsocketConfig:
    type: str
    resub_timeout_ms: Optional[int] = None
    commitment: Optional[Commitment] = None

@dataclass
class UserMapConfig:
    drift_client: DriftClient
    subscription_config: Union[PollingConfig, WebsocketConfig]
    # connection object to use specifically for the UserMap.  
    # If None, will use the drift_client's connection
    connection: Optional[AsyncClient] = None
    # True to skip the initial load of user_accounts via gPA
    skip_initial_load: Optional[bool] = None
    # True to include idle users when loading.
    # Defaults to false to decrease # of accounts subscribed to
    include_idle: Optional[bool] = None
