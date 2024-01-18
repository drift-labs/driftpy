import asyncio
import base64
import traceback

from typing import Dict, Optional, Union
import jsonrpcclient

from solana.rpc.commitment import Confirmed
from solders.pubkey import Pubkey
from driftpy.accounts.types import DataAndSlot
from driftpy.decode.utils import decode_name

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
            config.skip_initial_load,
            config.subscription_config.resub_timeout_ms,
            config.program.coder.accounts.decode,
        )

        self.latest_slot = 0
        self.is_subscribed = False

    def init(self, market_ds: list[DataAndSlot[GenericMarketType]]):
        for data_and_slot in market_ds:
            self.market_map[data_and_slot.data.market_index] = data_and_slot

    async def subscribe(self):
        if self.size() > 0:
            return

        await self.subscription.subscribe()
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
            pubkey = Pubkey.from_string(key, data)
            await self.add_pubkey(pubkey)
        return self.get(key)

    def size(self) -> int:
        return len(self.market_map)

    def values(self):
        return iter(self.market_map.values())

    async def add_market(
        self, market_index: int, data: DataAndSlot[GenericMarketType]
    ) -> None:
        self.market_map[market_index] = data

    async def sync(self) -> None:
        async with self.sync_lock:
            try:
                memcmp_opts = get_market_type_filter(self.market_type)
                filters = [{"memcmp": {"offset": 0, "bytes": f"{memcmp_opts.bytes}"}}]

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

                resp = await asyncio.wait_for(post, timeout=10)

                parsed_resp = jsonrpcclient.parse(resp.json())

                slot = int(parsed_resp.result["context"]["slot"])

                self.latest_slot = slot

                rpc_response_values = parsed_resp.result["value"]

                program_account_buffer_map: Dict[str, GenericMarketType] = {}

                # parse the gPA data before inserting
                for program_account in rpc_response_values:
                    pubkey = program_account["pubkey"]
                    buffer = base64.b64decode(program_account["account"]["data"][0])
                    data = self.program.coder.accounts.decode(buffer)
                    program_account_buffer_map[str(pubkey)] = data

                # "idempotent" insert into marketmap
                for pubkey in program_account_buffer_map.keys():
                    data = program_account_buffer_map.get(pubkey)
                    if pubkey not in self.market_map:
                        await self.add_market(
                            data.market_index, DataAndSlot(slot, data)
                        )
                    else:
                        self.update_market(pubkey, DataAndSlot(slot, data))

                    await asyncio.sleep(0)

                keys_to_delete = []
                for key in list(self.market_map.keys()):
                    if key not in program_account_buffer_map:
                        keys_to_delete.append(key)
                    await asyncio.sleep(0)

                for key in keys_to_delete:
                    del self.market_map[key]

            except Exception as e:
                print(f"Error in MarketMap.sync(): {e}")
                traceback.print_exc()

    async def update_market(
        self, _key: str, data: DataAndSlot[GenericMarketType]
    ) -> None:
        await self.must_get(data.data.market_index, data)
        self.market_map[data.data.market_index] = data
