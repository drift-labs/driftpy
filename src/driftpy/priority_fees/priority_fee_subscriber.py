import asyncio
from dataclasses import dataclass

import jsonrpcclient
from solana.rpc.async_api import AsyncClient


@dataclass
class PriorityFeeConfig:
    connection: AsyncClient
    frequency_secs: int
    addresses: list[str]
    slots_to_check: int = 10


class PriorityFeeSubscriber:
    def __init__(self, config: PriorityFeeConfig):
        self.connection = config.connection
        self.frequency_ms = config.frequency_secs
        self.addresses = config.addresses
        self.slots_to_check = config.slots_to_check

        self.latest_priority_fee = 0
        self.avg_priority_fee = 0
        self.max_priority_fee = 0
        self.last_slot_seen = 0
        self.subscribed = False

    async def subscribe(self):
        if self.subscribed:
            return

        self.subscribed = True

        asyncio.create_task(self.poll())

    async def poll(self):
        while self.subscribed:
            asyncio.create_task(self.load())
            await asyncio.sleep(self.frequency_ms)

    async def load(self):
        rpc_request = jsonrpcclient.request(
            "getRecentPrioritizationFees", [self.addresses]
        )

        post = self.connection._provider.session.post(
            self.connection._provider.endpoint_uri,
            json=rpc_request,
            headers={"content-encoding": "gzip"},
        )

        resp = await asyncio.wait_for(post, timeout=20)

        parsed_resp = jsonrpcclient.parse(resp.json())

        if isinstance(parsed_resp, jsonrpcclient.Error):
            raise ValueError(f"Error fetching priority fees: {parsed_resp.message}")

        if not isinstance(parsed_resp, jsonrpcclient.Ok):
            raise ValueError(f"Error fetching priority fees - not ok: {parsed_resp}")

        result = parsed_resp.result

        desc_results = sorted(result, key=lambda x: x["slot"], reverse=True)[
            : self.slots_to_check
        ]

        if not desc_results:
            return

        self.latest_priority_fee = desc_results[0]["prioritizationFee"]
        self.last_slot_seen = desc_results[0]["slot"]
        self.avg_priority_fee = sum(
            item["prioritizationFee"] for item in desc_results
        ) / len(desc_results)
        self.max_priority_fee = max(item["prioritizationFee"] for item in desc_results)

    async def unsubscribe(self):
        if self.subscribed:
            self.subscribed = False
