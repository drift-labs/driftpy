import asyncio
import json
import traceback
from typing import Optional
import aiohttp
from events import Events as EventEmitter
from dataclasses import dataclass
from solders.pubkey import Pubkey
from driftpy.dlob.client_types import DLOBClientConfig
from driftpy.dlob.orderbook_levels import (
    DEFAULT_TOP_OF_BOOK_QUOTE_AMOUNTS,
    L3Level,
    L3OrderBook,
    L2Level,
    L2OrderBook,
    L2OrderBookGenerator,
    get_vamm_l2_generator,
)
from driftpy.types import (
    MarketType,
    is_variant,
)


@dataclass
class MarketId:
    index: int
    kind: MarketType


class DLOBSubscriber:
    _session: Optional[aiohttp.ClientSession] = None

    def __init__(
        self,
        url: Optional[str] = None,  # Provide this if using DLOB server
        config: Optional[
            DLOBClientConfig
        ] = None,  # Provide this if building from usermap
    ):
        if url:
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
        This function CANNOT be used unless a `DLOBClientConfig` was provided in the `DLOBClient`'s constructor.
        If it is used without a `DLOBClientConfig`, it will return nothing.
        """
        if not all([self.dlob_source, self.slot_source, self.drift_client]):
            return

        if self.interval_task is not None:
            return

        await self.update_dlob()

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

    def get_l2_orderbook_sync(
        self,
        market_name: Optional[str] = None,
        market_index: Optional[int] = None,
        market_type: Optional[MarketType] = None,
        include_vamm: Optional[bool] = False,
        num_vamm_orders: Optional[int] = None,
        fallback_l2_generators: Optional[L2OrderBookGenerator] = [],
        depth: Optional[int] = 10,
    ) -> L2OrderBook:
        if market_name:
            derived_market_info = self.drift_client.get_market_index_and_type(
                market_name
            )
            if not derived_market_info:
                raise ValueError(
                    f"Market index and type for {market_name} could not be found."
                )
            market_index = derived_market_info[0]
            market_type = derived_market_info[1]
        else:
            if market_index is None or market_type is None:
                raise ValueError(
                    "Either market_name or market_index and market_type must be provided"
                )

        market_is_perp = is_variant(market_type, "Perp")
        if market_is_perp:
            oracle_price_data = self.drift_client.get_oracle_price_data_for_perp_market(
                market_index
            )
        else:
            oracle_price_data = self.drift_client.get_oracle_price_data_for_spot_market(
                market_index
            )

        if market_is_perp and include_vamm:
            if not fallback_l2_generators:
                fallback_l2_generators = []
            if len(fallback_l2_generators) > 0:
                raise ValueError(
                    "include_vamm can only be used if fallback_l2_generators is empty"
                )

            fallback_l2_generators = [
                get_vamm_l2_generator(
                    self.drift_client.get_perp_market_account(market_index),
                    oracle_price_data,
                    num_vamm_orders if num_vamm_orders is not None else depth,
                    DEFAULT_TOP_OF_BOOK_QUOTE_AMOUNTS,
                )
            ]

        return self.dlob.get_l2(
            market_index,
            market_type,
            self.slot_source.get_slot(),
            oracle_price_data,
            depth,
            fallback_l2_generators,
        )

    def get_l3_orderbook_sync(
        self,
        market_name: Optional[str] = None,
        market_index: Optional[int] = None,
        market_type: Optional[MarketType] = None,
    ) -> L3OrderBook:
        if market_name:
            derived_market_info = self.drift_client.get_market_index_and_type(
                market_name
            )
            if not derived_market_info:
                raise ValueError(
                    f"Market index and type for {market_name} could not be found."
                )
            market_index = derived_market_info[0]
            market_type = derived_market_info[1]
        else:
            if market_index is None or market_type is None:
                raise ValueError(
                    "Either market_name or market_index and market_type must be provided"
                )

        market_is_perp = is_variant(market_type, "Perp")
        if market_is_perp:
            oracle_price_data = self.drift_client.get_oracle_price_data_for_perp_market(
                market_index
            )
        else:
            oracle_price_data = self.drift_client.get_oracle_price_data_for_spot_market(
                market_index
            )

        return self.dlob.get_l3(
            market_index, market_type, self.slot_source.get_slot(), oracle_price_data
        )
