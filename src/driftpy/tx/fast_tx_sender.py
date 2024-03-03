import asyncio

from solders.hash import Hash

from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Commitment, Confirmed

from driftpy.tx.standard_tx_sender import StandardTxSender


class FastTxSender(StandardTxSender):
    """
    The FastTxSender will refresh the latest blockhash in the background to save an RPC when building transactions.
    """

    def __init__(
        self,
        connection: AsyncClient,
        opts: TxOpts,
        blockhash_refresh_interval_secs: int,
        blockhash_commitment: Commitment = Confirmed,
    ):
        super().__init__(connection, opts, blockhash_commitment)
        self.blockhash_refresh_interval = blockhash_refresh_interval_secs
        self.recent_blockhash = None

    async def subscribe_blockhash(self):
        """
        Must be called with asyncio.create_task to prevent blocking
        """
        while True:
            try:
                blockhash_info = await self.connection.get_latest_blockhash(
                    self.blockhash_commitment
                )
                self.recent_blockhash = blockhash_info.value.blockhash
            except Exception as e:
                print(f"Error in subscribe_blockhash: {e}")
            await asyncio.sleep(self.blockhash_refresh_interval)

    async def fetch_latest_blockhash(self) -> Hash:
        if self.recent_blockhash is None:
            asyncio.create_task(self.subscribe_blockhash())
            return await super().get_blockhash()
        return self.recent_blockhash
