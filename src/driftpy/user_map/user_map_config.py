from dataclasses import dataclass
from typing import Literal, Optional, Union

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment

from driftpy.drift_client import DriftClient


@dataclass
class UserAccountFilterCriteria:
    # only return users that have open orders
    has_open_orders: bool


@dataclass
class PollingConfig:
    frequency: int
    commitment: Optional[Commitment] = None


@dataclass
class WebsocketConfig:
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
    skip_initial_load: Optional[bool] = False
    # True to include idle users when loading.
    # Defaults to false to decrease # of accounts subscribed to
    include_idle: Optional[bool] = None


@dataclass
class SyncConfig:
    type: Literal["default", "paginated"]
    chunk_size: Optional[int] = None
    concurrency_limit: Optional[int] = None


@dataclass
class UserStatsMapConfig:
    drift_client: DriftClient
    connection: Optional[AsyncClient] = None
    sync_config: Optional[SyncConfig] = None
