import asyncio
import base64
import traceback

from typing import Dict, Optional, Union
import jsonrpcclient

from solana.rpc.commitment import Confirmed
from driftpy.accounts.types import DataAndSlot

from driftpy.market_map.market_map_config import MarketMapConfig
from driftpy.market_map.websocket_sub import WebsocketSubscription
from driftpy.memcmp import get_market_type_filter
from driftpy.types import PerpMarketAccount, SpotMarketAccount, is_variant

GenericMarketType = Union[SpotMarketAccount, PerpMarketAccount]


class MarketMap:
    def __init__(self, config: MarketMapConfig):
        if is_variant(config.market_type, "Perp"):
            self.market_map: Dict[str, PerpMarketAccount] = {}
        else:
            self.market_map: Dict[str, SpotMarketAccount] = {}
        self.program = config.program
        self.market_type = config.market_type
        self.sync_lock = asyncio.Lock()
        self.connection = config.connection
        self.commitment = config.subscription_config.commitment or Confirmed

        self.subscription = WebsocketSubscription(
            self,
            self.commitment,
            self.update_market,
            config.subscription_config.resub_timeout_ms,
            config.program.coder.accounts.decode,
        )

        self.latest_slot = 0
        self.is_subscribed = False

    def init(self, market_ds: list[DataAndSlot[GenericMarketType]]):
        for data_and_slot in market_ds:
            self.market_map[data_and_slot.data.market_index] = data_and_slot

    async def subscribe(self):
        if self.is_subscribed:
            return

        asyncio.create_task(self.subscription.subscribe())
        self.is_subscribed = True

    async def unsubscribe(self):
        await self.subscription.unsubscribe()

        for key in list(self.market_map.keys()):
            del self.market_map[key]

        self.is_subscribed = False

    def has(self, key: int) -> bool:
        return key in self.market_map

    def get(self, key: int) -> Optional[GenericMarketType]:
        return self.market_map.get(key)

    async def must_get(
        self, key: int, data: DataAndSlot[GenericMarketType]
    ) -> Optional[GenericMarketType]:
        if not self.has(key):
            await self.add_market(key, data)
        return self.get(key)

    def size(self) -> int:
        return len(self.market_map)

    def values(self):
        return iter(self.market_map.values())

    async def add_market(
        self, market_index: int, data: DataAndSlot[GenericMarketType]
    ) -> None:
        self.market_map[market_index] = data

    async def update_market(
        self, _key: str, data: DataAndSlot[GenericMarketType]
    ) -> None:
        await self.must_get(data.data.market_index, data)
        self.market_map[data.data.market_index] = data
