import asyncio

from events import Events as EventEmitter
from solana.rpc.websocket_api import SolanaWsClientProtocol, connect

from driftpy.dlob.client_types import SlotSource
from driftpy.drift_client import DriftClient
from driftpy.types import get_ws_url


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

    async def on_slot_change(self, slot_info: int):
        self.current_slot = slot_info
        self.event_emitter.on_slot_change(slot_info)

    async def subscribe(self):
        if self.subscribed:
            return
        self.task = asyncio.create_task(self.subscribe_ws())
        return self.task

    async def subscribe_ws(self):
        if self.subscription_id is not None:
            return

        current_slot_response = await self.connection.get_slot()
        self.current_slot = int(current_slot_response.value)

        endpoint = self.program.provider.connection._provider.endpoint_uri
        ws_endpoint = get_ws_url(endpoint)
        while True:
            try:
                async with connect(ws_endpoint) as ws:
                    self.subscribed = True
                    self.ws = ws
                    ws: SolanaWsClientProtocol
                    self.subscription_id = await ws.slot_subscribe()

                    await ws.recv()

                    async for msg in ws:
                        await self.on_slot_change(msg[0].result.slot)

            except Exception as e:
                print(f"Error in SlotSubscriber: {e}")
                if self.ws:
                    await self.ws.close()
                    self.ws = None
                await asyncio.sleep(5)  # wait a second before we retry

    def get_slot(self) -> int:
        return self.current_slot

    async def unsubscribe(self):
        if self.ws:
            await self.ws.close()
            self.ws = None
        self.subscribed = False
