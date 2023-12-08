import asyncio
import websockets

class WebsocketSubscription:
    def __init__(
            self, 
            user_map, 
            commitment, 
            skip_initial_load: bool = False,
            resub_timeout_ms: int = None,
            include_idle: bool = False,
        ):
        self.user_map = user_map
        self.commitment = commitment
        self.skip_initial_load = skip_initial_load
        self.resub_timeout_ms = resub_timeout_ms
        self.include_idle = include_idle
        self.subscriber = None

    async def subscribe(self):
        # TODO
        # I don't think I need this for the Liquidator so I'm leaving it TODO for now
        pass

    async def unsubscribe(self):
        if not self.subscriber:
            return
        await self.subscriber.unsubscribe()
        self.subscriber = None