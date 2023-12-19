
import asyncio

from solana.rpc.websocket_api import connect, SolanaWsClientProtocol

from driftpy.drift_client import DriftClient

class SlotSubscriber:
    def __init__(self, drift_client: DriftClient):
        self.current_slot = 0
        self.subscription_id = None
        self.connection = drift_client.connection
        self.program = drift_client.program
        self.ws = None
        self.subscribed = False

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
        ws_endpoint = endpoint.replace('https', 'wss').replace('http', 'ws')
        while True:
            try:
                async with connect(ws_endpoint) as ws:
                    self.subscribed = True
                    self.ws = ws
                    ws: SolanaWsClientProtocol
                    self.subscription_id = await ws.slot_subscribe()

                    await ws.recv()

                    async for msg in ws:
                        print(f"Received message: {msg}")
            except Exception as e:
                print(f"Error in SlotSubscriber: {e}")
                await self.ws.close()
                self.ws = None
                await asyncio.sleep(5) # wait a second before we retry

    def get_slot(self) -> int:
        return self.current_slot

    async def unsubscribe(self):
        if self.ws:
            self.ws.close()
            self.ws = None
        self.subscribed = False
