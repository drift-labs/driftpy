import asyncio
import websockets
from driftpy.memcmp import get_user_filter, get_non_idle_user_filter
from driftpy.accounts.ws import WebsocketUserAccountSubscriber

class WebsocketSubscription:
    def __init__(
            self, 
            user_map, 
            commitment, 
            skip_initial_load: bool = False,
            resub_timeout_ms: int = None,
            include_idle: bool = False,
        ):

        from driftpy.user_map.user_map import UserMap

        self.user_map: UserMap = user_map
        self.commitment = commitment
        self.skip_initial_load = skip_initial_load
        self.resub_timeout_ms = resub_timeout_ms
        self.include_idle = include_idle
        self.subscriber = None

    async def subscribe(self):
        if not self.subscriber:
            filters = (get_user_filter(),)
            if not self.include_idle:
                filters += (get_non_idle_user_filter(),)
            # self.subscriber = WebsocketUserAccountSubscriber(test, self.user_map.drift_client.program, self.commitment)

    async def unsubscribe(self):
        if not self.subscriber:
            return
        await self.subscriber.unsubscribe()
        self.subscriber = None