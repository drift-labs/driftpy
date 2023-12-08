import threading

class PollingSubscription:
    def __init__(self, user_map, frequency: float, skip_initial_load: bool = False):
        self.user_map = user_map
        self.frequency = frequency
        self.skip_initial_load = skip_initial_load
        self.interval_id = None

    async def subscribe(self):
        if self.interval_id is not None:
            return
        
        self.interval_id = threading.Event()
        self._start_polling()

        if not self.skip_initial_load:
            await self.user_map.sync()
        
    def _start_polling(self):
        if self.interval_id.is_set():
            return
        
        threading.Timer(self.frequency, self._sync_and_reschedule).start()

    async def _sync_and_reschedule(self):
        await self.user_map.sync()
        self._start_polling()

    async def unsubscribe(self):
        if self.interval_id is not None:
            self.interval_id.set()
            self.interval_id = None