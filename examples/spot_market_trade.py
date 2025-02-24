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
        env="mainnet",
        tx_params=TxParams(compute_units_price=85_000, compute_units=1_400_000),
    )
    await drift_client.subscribe()

    logger.info("Drift client subscribed")

    market_symbol_1 = "JLP"
    market_symbol_2 = "USDC"

    in_decimals_result = drift_client.get_spot_market_account(
        get_market_by_symbol(market_symbol_1).market_index
    )
    if not in_decimals_result:
        logger.error("USDS market not found")
        raise Exception("Market not found")

    in_decimals = in_decimals_result.decimals
    logger.info(f"{market_symbol_1} decimals: {in_decimals}")

    swap_amount = int(1 * 10**in_decimals)
    logger.info(f"Swapping {swap_amount} {market_symbol_1} to {market_symbol_2}")

    swap_ixs, swap_lookups = await drift_client.get_jupiter_swap_ix_v6(
        out_market_idx=get_market_by_symbol(market_symbol_2).market_index,
        in_market_idx=get_market_by_symbol(market_symbol_1).market_index,
        amount=swap_amount,
        swap_mode="ExactIn",
        only_direct_routes=True,
        max_accounts=20,
    )
    await drift_client.send_ixs(
        ixs=swap_ixs,
        lookup_tables=swap_lookups,
    )
    logger.info("Swap complete")


if __name__ == "__main__":
    asyncio.run(make_spot_trade())
