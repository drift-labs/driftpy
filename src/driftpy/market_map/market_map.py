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
        self.market_type = config.market_type
        self.sync_lock = asyncio.Lock()
        self.drift_client = config.drift_client
        self.connection = config.connection or config.drift_client.connection
        self.commitment = config.subscription_config.commitment or Confirmed

        self.subscription = WebsocketSubscription(
            self,
            self.commitment,
            self.update_market,
            config.skip_initial_load,
            config.subscription_config.resub_timeout_ms,
            self.drift_client.program.coder.accounts.decode,
        )

        self.latest_slot = 0
        self.is_subscribed = False

    async def subscribe(self):
        if self.size() > 0:
            return

        await self.drift_client.subscribe()
        await self.subscription.subscribe()
        self.is_subscribed = True

    async def unsubscribe(self):
        await self.subscription.unsubscribe()

        for key in list(self.market_map.keys()):
            del self.market_map[key]

        self.is_subscribed = False

    def has(self, key: str) -> bool:
        return key in self.market_map

    def get(self, key: str) -> Optional[GenericMarketType]:
        return self.market_map.get(key)

    async def must_get(self, key: str) -> Optional[GenericMarketType]:
        if not self.has(key):
            pubkey = Pubkey.from_string(key)
            await self.add_pubkey(pubkey)
        return self.get(key)

    def size(self) -> int:
        return len(self.market_map)

    def values(self):
        return iter(self.market_map.values())

    async def add_pubkey(
        self, market_public_key: Pubkey, data: Optional[DataAndSlot[GenericMarketType]]
    ) -> None:
        self.market_map[str(market_public_key)] = data

    async def sync(self) -> None:
        async with self.sync_lock:
            try:
                memcmp_opts = get_market_type_filter(self.market_type)
                filters = [{"memcmp": {"offset": 0, "bytes": f"{memcmp_opts.bytes}"}}]

                rpc_request = jsonrpcclient.request(
                    "getProgramAccounts",
                    [
                        str(self.drift_client.program_id),
                        {"filters": filters, "encoding": "base64", "withContext": True},
                    ],
                )

                post = self.drift_client.connection._provider.session.post(
                    self.drift_client.connection._provider.endpoint_uri,
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
                    data = self.drift_client.program.coder.accounts.decode(buffer)
                    program_account_buffer_map[str(pubkey)] = data

                # "idempotent" insert into marketmap
                for pubkey in program_account_buffer_map.keys():
                    data = program_account_buffer_map.get(pubkey)
                    if pubkey not in self.market_map:
                        await self.add_pubkey(
                            Pubkey.from_string(pubkey), DataAndSlot(slot, data)
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
        self, key: str, data: DataAndSlot[GenericMarketType]
    ) -> None:
        print(f"Updating market: {decode_name(data.data.name)}")
        await self.must_get(key)
        self.market_map[key] = [data]