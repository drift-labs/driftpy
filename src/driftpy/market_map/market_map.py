import asyncio
import base64
import os
import pickle
import traceback

from typing import Dict, Optional, Union
import jsonrpcclient

from solana.rpc.commitment import Confirmed
from driftpy.accounts.types import DataAndSlot

from driftpy.market_map.market_map_config import MarketMapConfig
from driftpy.market_map.websocket_sub import WebsocketSubscription
from driftpy.types import (
    PerpMarketAccount,
    PickledData,
    SpotMarketAccount,
    is_variant,
    compress,
    decompress,
    market_type_to_string,
)

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

    def clear(self):
        self.market_map.clear()

    def get_last_dump_filepath(self) -> str:
        return f"{market_type_to_string(self.market_type)}_{self.latest_slot}.pkl"

    async def dump(self):
        try:
            filters = []
            if is_variant(self.market_type, "Perp"):
                filters.append({"memcmp": {"offset": 0, "bytes": "2pTyMkwXuti"}})
            else:
                filters.append({"memcmp": {"offset": 0, "bytes": "HqqNdyfVbzv"}})

            rpc_request = jsonrpcclient.request(
                "getProgramAccounts",
                [
                    str(self.program.program_id),
                    {"filters": filters, "encoding": "base64", "withContext": True},
                ],
            )

            post = self.connection._provider.session.post(
                self.connection._provider.endpoint_uri,
                json=rpc_request,
                headers={"content-encoding": "gzip"},
            )

            resp = await asyncio.wait_for(post, timeout=30)

            parsed_resp = jsonrpcclient.parse(resp.json())

            slot = int(parsed_resp.result["context"]["slot"])

            self.latest_slot = slot

            rpc_response_values = parsed_resp.result["value"]

            raw: Dict[str, bytes] = {}

            for market in rpc_response_values:
                pubkey = market["pubkey"]
                raw_bytes = base64.b64decode(market["account"]["data"][0])
                raw[str(pubkey)] = raw_bytes

            markets = []
            for pubkey, market in raw.items():
                markets.append(PickledData(pubkey=pubkey, data=compress(market)))
            filename = (
                f"{market_type_to_string(self.market_type)}_{self.latest_slot}.pkl"
            )
            with open(filename, "wb") as f:
                pickle.dump(markets, f)

        except Exception as e:
            print(f"error in marketmap pickle: {e}")

    async def load(self, filename: Optional[str] = None):
        if not filename:
            filename = self.get_last_dump_filepath()
        if not os.path.exists(filename):
            raise FileNotFoundError(f"File {filename} not found")
        start = filename.index("_") + 1
        end = filename.index(".")
        slot = int(filename[start:end])
        with open(filename, "rb") as f:
            markets: list[PickledData] = pickle.load(f)
            for market in markets:
                data = self.program.coder.accounts.decode(decompress(market.data))
                await self.add_market(data.market_index, DataAndSlot(slot, data))
