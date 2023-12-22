import asyncio
import json
from typing import Optional
import aiohttp
from dataclasses import dataclass
from solders.pubkey import Pubkey
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

    def __init__(self, url: str):
        self.url = url.rstrip("/")

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
