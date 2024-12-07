import asyncio
from driftpy.user_map.types import Subscription


class PollingSubscription(Subscription):
    def __init__(self, user_map, frequency: float, skip_initial_load: bool = False):
        from driftpy.user_map.user_map import UserMap

        self.user_map: UserMap = user_map
        self.frequency = frequency
        self.skip_initial_load = skip_initial_load
        self.timer_task = None

    async def subscribe(self):
        if self.timer_task is not None:
            return

        if not self.skip_initial_load:
            await self.user_map.sync()

        self.timer_task = asyncio.create_task(self._polling_loop())

    async def _polling_loop(self):
        if self.frequency == 0:
            # We don't want to start this loop if the frequency is zero.
            return
        while True:
            await asyncio.sleep(self.frequency)
            await self.user_map.sync()

    async def unsubscribe(self):
        if self.timer_task is not None:
            self.timer_task.cancel()
            self.timer_task = None
