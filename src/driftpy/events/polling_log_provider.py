import asyncio
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment

from solders.pubkey import Pubkey

from driftpy.events.fetch_logs import fetch_logs
from driftpy.events.types import LogProvider, LogProviderCallback


class PollingLogProvider(LogProvider):
    def __init__(
        self,
        connection: AsyncClient,
        address: Pubkey,
        commitment: Commitment,
        frequency: float,
        batch_size: int = 25,
    ):
        self.connection = connection
        self.address = address
        self.commitment = commitment
        self.frequency = frequency
        self.batch_size = batch_size
        self.task = None
        self.most_recent_tx = None

    def subscribe(self, callback: LogProviderCallback):
        if not self.is_subscribed():

            async def fetch():
                first_fetch = True
                while True:
                    try:
                        txs_logs = await fetch_logs(
                            self.connection,
                            self.address,
                            self.commitment,
                            None,
                            self.most_recent_tx,
                            1 if first_fetch else None,
                            self.batch_size,
                        )

                        for signature, slot, logs in txs_logs:
                            callback(signature, slot, logs)

                        first_fetch = False
                    except Exception as e:
                        print("Error fetching logs", e)

                    await asyncio.sleep(self.frequency)

            self.task = asyncio.create_task(fetch())

    def is_subscribed(self) -> bool:
        return self.task is not None

    def unsubscribe(self):
        if self.is_subscribed():
            self.task.cancel()
            self.task = None
