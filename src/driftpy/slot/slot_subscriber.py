import asyncio
import random

from solana.rpc.websocket_api import connect, SolanaWsClientProtocol
from driftpy.dlob.client_types import SlotSource
from driftpy.types import get_ws_url

from driftpy.drift_client import DriftClient
from events import Events as EventEmitter

MAX_FAILURES = 10
MAX_DELAY = 16


class SlotSubscriber(SlotSource):
    def __init__(self, drift_client: DriftClient):
        self.current_slot = 0
        self.subscription_id = None
        self.connection = drift_client.connection
        self.program = drift_client.program
        self.ws = None
        self.subscribed = False
        self.event_emitter = EventEmitter(("on_slot_change"))
        self.event_emitter.on("on_slot_change")

    async def on_slot_change(self, slot_info):
        self.current_slot = slot_info.slot
        self.event_emitter.on_slot_change(slot_info.slot)

    async def subscribe(self):
        if self.subscribed:
            return
        self.task = asyncio.create_task(self.subscribe_ws())
        return self.task

    async def subscribe_ws(self):
        if self.subscription_id is not None:
            return

        self.current_slot = await self.connection.get_slot()

        endpoint = self.program.provider.connection._provider.endpoint_uri
        ws_endpoint = get_ws_url(endpoint)
        num_failures = 0
        delay = 1
        while True:
            try:
                async with connect(ws_endpoint) as ws:
                    self.subscribed = True
                    self.ws = ws
                    ws: SolanaWsClientProtocol
                    self.subscription_id = await ws.slot_subscribe()

                    await ws.recv()

                    async for msg in ws:
                        await self.on_slot_change(msg[0].result)

            except Exception as e:
                print(f"Error in SlotSubscriber: {e}")
                num_failures += 1
                if num_failures >= MAX_FAILURES:
                    print(f"Max failures reached for SlotSubscriber, unsubscribing")
                    await self.unsubscribe()
                    break
                if self.ws:
                    await self.ws.close()
                    self.ws = None
                await asyncio.sleep(
                    delay
                )  # wait a second before we retry, exponential backoff
                delay = min(delay * 2, MAX_DELAY)
                delay += delay * random.uniform(-0.1, 0.1)  # add some jitter

    def get_slot(self) -> int:
        return self.current_slot

    async def unsubscribe(self):
        if self.ws:
            await self.ws.close()
            self.ws = None
        self.subscribed = False
