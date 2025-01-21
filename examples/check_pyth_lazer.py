import asyncio
import os

from anchorpy.provider import Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient

from driftpy.drift_client import DriftClient
from driftpy.types import is_variant


async def main():
    load_dotenv()
    url = os.getenv("DEVNET_RPC_ENDPOINT", "https://api.devnet.solana.com")
    connection = AsyncClient(url)
    print("RPC URL:", url)

    print("Checking devnet constants")
    drift_client = DriftClient(
        connection,
        Wallet.dummy(),
        env="devnet",
    )

    print("Subscribing to Drift Client")
    await drift_client.subscribe()
    received_perp_markets = sorted(
        drift_client.get_perp_market_accounts(), key=lambda market: market.market_index
    )
    for market in received_perp_markets:
        oracle_data = drift_client.get_user().get_oracle_data_for_perp_market(
            market.market_index
        )
        if oracle_data and (
            is_variant(market.amm.oracle_source, "PythLazer")
            or is_variant(market.amm.oracle_source, "PythLazer1K")
            or is_variant(market.amm.oracle_source, "PythLazer1M")
        ):
            print(
                market.market_index,
                market.amm.oracle,
                bytes(market.name).decode("utf-8").strip(),
                market.amm.oracle_source,
                oracle_data.price / 10**6,
            )

    print("Subscribed to Drift Client")
    await drift_client.unsubscribe()
    await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
