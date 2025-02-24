import asyncio
import logging
import os

import dotenv
from anchorpy.provider import Wallet
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair

from driftpy.accounts.ws.drift_client import WebsocketDriftClientAccountSubscriber
from driftpy.drift_client import DriftClient
from driftpy.keypair import load_keypair
from driftpy.types import (
    TxParams,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


async def get_all_spot_indexes(rpc_url: str):
    throwaway_drift_client = DriftClient(
        connection=AsyncClient(rpc_url),
        wallet=Wallet(Keypair()),
        env="mainnet",
        spot_market_indexes=[],
    )
    spot_markets = await throwaway_drift_client.program.account["SpotMarket"].all()
    await throwaway_drift_client.unsubscribe()
    await throwaway_drift_client.connection.close()
    return [market.account.market_index for market in spot_markets]


async def get_all_perp_indexes(rpc_url: str):
    throwaway_drift_client = DriftClient(
        connection=AsyncClient(rpc_url),
        wallet=Wallet(Keypair()),
        env="mainnet",
        perp_market_indexes=[],
    )
    perp_markets = await throwaway_drift_client.program.account["PerpMarket"].all()
    await throwaway_drift_client.unsubscribe()
    await throwaway_drift_client.connection.close()
    return [market.account.market_index for market in perp_markets]


async def main():
    logger.info("Starting...")
    dotenv.load_dotenv()
    rpc_url = os.getenv("RPC_TRITON")
    private_key = os.getenv("PRIVATE_KEY")
    if not rpc_url or not private_key:
        raise Exception("Missing env vars")
    kp = load_keypair(private_key)

    drift_client = DriftClient(
        connection=AsyncClient(rpc_url),
        wallet=Wallet(kp),
        env="mainnet",
        tx_params=TxParams(700_000, 10_000),
    )
    await drift_client.subscribe()
    perp_markets = drift_client.get_perp_market_account(65)
    if perp_markets is None:
        raise Exception("No perp markets found")
    print(perp_markets)

    try:
        if not isinstance(
            drift_client.account_subscriber, WebsocketDriftClientAccountSubscriber
        ):
            raise Exception("Account subscriber is not a WebsocketAccountSubscriber")
        while True:
            print(perp_markets.amm.historical_oracle_data.last_oracle_price / 1e6)
            await asyncio.sleep(5)
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Exiting loop...")
    finally:
        await drift_client.unsubscribe()
        await drift_client.connection.close()
        logger.info("Unsubscribed from Drift client.")


if __name__ == "__main__":
    asyncio.run(main())
