import asyncio
import logging
import os

from anchorpy.provider import Provider, Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient

from driftpy.constants.spot_markets import mainnet_spot_market_configs
from driftpy.drift_client import DriftClient
from driftpy.keypair import load_keypair
from driftpy.types import TxParams

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


def get_market_by_symbol(symbol: str):
    for market in mainnet_spot_market_configs:
        if market.symbol == symbol:
            return market
    raise Exception(f"Market {symbol} not found")


async def make_spot_trade():
    rpc = os.environ.get("RPC_TRITON")
    secret = os.environ.get("PRIVATE_KEY")
    kp = load_keypair(secret)
    wallet = Wallet(kp)
    logger.info(f"Using wallet: {wallet.public_key}")

    connection = AsyncClient(rpc)
    provider = Provider(connection, wallet)
    drift_client = DriftClient(
        provider.connection,
        provider.wallet,
        "mainnet",
        tx_params=TxParams(
            compute_units_price=85_000,
            compute_units=1_000_000,
        ),
    )
    await drift_client.subscribe()
    logger.info("Drift client subscribed")

    in_decimals_result = drift_client.get_spot_market_account(
        get_market_by_symbol("USDS").market_index
    )
    if not in_decimals_result:
        logger.error("USDS market not found")
        raise Exception("Market not found")

    in_decimals = in_decimals_result.decimals
    logger.info(f"USDS decimals: {in_decimals}")

    swap_amount = int(1 * 10**in_decimals)
    logger.info(f"Swapping {swap_amount} USDS to USDC")

    try:
        swap_ixs, swap_lookups = await drift_client.get_jupiter_swap_ix_v6(
            out_market_idx=get_market_by_symbol("USDC").market_index,
            in_market_idx=get_market_by_symbol("USDS").market_index,
            amount=swap_amount,
            swap_mode="ExactIn",
            only_direct_routes=True,
        )
        logger.info("Got swap instructions")
        print("[DEBUG] Got swap instructions of length", len(swap_ixs))

        await drift_client.send_ixs(
            ixs=swap_ixs,
            lookup_tables=swap_lookups,
        )
        logger.info("Swap complete")
    except Exception as e:
        logger.error(f"Error during swap: {e}")
        raise e
    finally:
        await drift_client.unsubscribe()
        await connection.close()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(make_spot_trade())
    finally:
        pending = asyncio.all_tasks(loop)
        loop.run_until_complete(asyncio.gather(*pending))
        loop.close()
