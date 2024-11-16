import asyncio
import os

from anchorpy import Wallet
from dotenv import load_dotenv
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.drift_client import DriftClient
from driftpy.keypair import load_keypair
from driftpy.types import OrderParams
from driftpy.types import OrderType
from driftpy.types import PositionDirection
from driftpy.types import PostOnlyParams
from driftpy.types import TxParams
from solana.rpc.async_api import AsyncClient


async def main():
    load_dotenv()
    url = os.getenv("DEVNET_RPC_ENDPOINT")
    connection = AsyncClient(url)
    print("RPC URL:", url)

    print("Checking devnet constants")
    drift_client = DriftClient(
        connection,
        Wallet.dummy(),
        env="devnet",
        account_subscription=AccountSubscriptionConfig("cached"),
    )

    print("Subscribing to Drift Client")

    await drift_client.subscribe()
    received_perp_markets = sorted(
        drift_client.get_perp_market_accounts(), key=lambda market: market.market_index
    )
    for market in received_perp_markets:
        print(market.market_index, market.amm.oracle)

    print("Subscribed to Drift Client")

    # Ensure proper cleanup
    await drift_client.unsubscribe()
    await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
