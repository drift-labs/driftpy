import asyncio
import json
import traceback
from typing import Optional
import aiohttp
from events import Events as EventEmitter
from dataclasses import dataclass
from solders.pubkey import Pubkey
from driftpy.dlob.client_types import DLOBClientConfig
from driftpy.dlob.orderbook_levels import L3Level, L3OrderBook, L2Level, L2OrderBook
from driftpy.types import (
    MarketType,
    is_variant,
)


@dataclass
class MarketId:
    index: int
    kind: MarketType


class DLOBClient:
    _session: Optional[aiohttp.ClientSession] = None

    def __init__(self, url: str, config: Optional[DLOBClientConfig] = None):
        self.url = url.rstrip("/")
        self.dlob = None
        self.event_emitter = EventEmitter(("on_dlob_update"))
        self.event_emitter.on("on_dlob_update")
        if config is not None:
            self.drift_client = config.drift_client
            self.dlob_source = config.dlob_source
            self.slot_source = config.slot_source
            self.update_frequency = config.update_frequency
            self.interval_task = None

    async def on_dlob_update(self):
        self.event_emitter.on_dlob_update(self.dlob)

    async def subscribe(self):
        """
        This function CANNOT be used unless a `DLOBClientConfig` was provided in the DLOBClient's constructor.
        If it is used without a `DLOBClientConfig`, it will break.
        """
        if self.interval_task is not None:
            return

        async def interval_loop():
            while True:
                try:
                    await self.update_dlob()
                    await self.on_dlob_update()
                except Exception as e:
                    print(f"Error in DLOB subscription: {e}")
                    traceback.print_exc()
                await asyncio.sleep(self.update_frequency)

        self.interval_task = asyncio.create_task(interval_loop())

    def unsubscribe(self):
        if self.interval_task is not None:
            self.interval_task.cancel()

    async def update_dlob(self):
        self.dlob = await self.dlob_source.get_DLOB(self.slot_source.get_slot())

    def get_dlob(self):
        return self.dlob

    @classmethod
    async def get_session(cls):
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession()
        return cls._session

    @classmethod
    async def close_session(cls):
        if cls._session is not None:
            await cls._session.close()
            cls._session = None

    async def get_l2_orderbook(self, market: MarketId) -> L2OrderBook:
        session = await self.get_session()
        market_type = "perp" if is_variant(market.kind, "Perp") else "spot"
        async with session.get(
            f"{self.url}/l2?marketType={market_type}&marketIndex={market.index}"
        ) as response:
            if response.status == 200:
                data = await response.text()
                return self.decode_l2_orderbook(data)
            else:
                raise Exception("Failed to fetch L2 OrderBook data")

    def decode_l2_orderbook(self, data: str) -> L2OrderBook:
        data = json.loads(data)

        asks = [
            L2Level(ask["price"], ask["size"], ask["sources"]) for ask in data["asks"]
        ]
        bids = [
            L2Level(bid["price"], bid["size"], bid["sources"]) for bid in data["bids"]
        ]
        slot = data.get("slot")

        return L2OrderBook(asks, bids, slot)

    async def get_l3_orderbook(self, market: MarketId) -> L3OrderBook:
        session = await self.get_session()
        market_type = "perp" if is_variant(market.kind, "Perp") else "spot"
        async with session.get(
            f"{self.url}/l3?marketType={market_type}&marketIndex={market.index}"
        ) as response:
            if response.status == 200:
                data = await response.text()
                return self.decode_l3_orderbook(data)
            else:
                raise Exception("Failed to fetch L3 OrderBook data")

    def decode_l3_orderbook(self, data: str) -> L3OrderBook:
        data = json.loads(data)

        asks = [
            L3Level(
                ask["price"],
                ask["size"],
                Pubkey.from_string(ask["maker"]),
                ask["orderId"],
            )
            for ask in data["asks"]
        ]
        bids = [
            L3Level(
                bid["price"],
                bid["size"],
                Pubkey.from_string(bid["maker"]),
                bid["orderId"],
            )
            for bid in data["bids"]
        ]
        slot = data.get("slot")

        return L3OrderBook(asks, bids, slot)

    async def subscribe_l2_book(self, market: MarketId, interval_s: int = 1):
        while True:
            try:
                orderbook = await self.get_l2_orderbook(market)
                yield orderbook
                await asyncio.sleep(interval_s)
            except Exception as e:
                print(f"Error fetching L2 OrderBook: {e}")
                break

    async def subscribe_l3_book(self, market: MarketId, interval_s: int = 1):
        while True:
            try:
                orderbook = await self.get_l3_orderbook(market)
                yield orderbook
                await asyncio.sleep(interval_s)
            except Exception as e:
                print(f"Error fetching L3 OrderBook: {e}")
                break
