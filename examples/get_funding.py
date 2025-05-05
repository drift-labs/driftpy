import asyncio
import os

from anchorpy.provider import Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient

from driftpy.accounts.get_accounts import get_perp_market_account
from driftpy.accounts.oracle import get_oracle_price_data_and_slot
from driftpy.constants import FUNDING_RATE_PRECISION, QUOTE_PRECISION
from driftpy.drift_client import DriftClient
from driftpy.math.funding import (
    calculate_live_mark_twap,
    calculate_long_short_funding_and_live_twaps,
)


async def main():
    load_dotenv()
    url = os.getenv("RPC_URL")
    connection = AsyncClient(url)
    dc = DriftClient(connection, Wallet.dummy(), "mainnet")
    await dc.subscribe()

    market = await get_perp_market_account(dc.program, 0)  # SOL-PERP
    if market is None:
        raise Exception("No market found")

    oracle_price = await get_oracle_price_data_and_slot(
        connection, market.amm.oracle, market.amm.oracle_source
    )
    oracle_price_data = oracle_price.data

    now = int(asyncio.get_event_loop().time())
    mark_price = market.amm.historical_oracle_data.last_oracle_price

    (
        mark_twap,
        oracle_twap,
        long_rate,
        short_rate,
    ) = await calculate_long_short_funding_and_live_twaps(
        market, oracle_price_data, mark_price, now
    )

    precision = FUNDING_RATE_PRECISION
    print(f"Long Funding Rate: {long_rate/precision}%")
    print(
        f"Last 24h Avg Funding Rate: {market.amm.last24h_avg_funding_rate/precision}%"
    )
    print(f"Last Funding Rate: {market.amm.last_funding_rate/precision}%")
    print(f"Last Funding Rate Long: {market.amm.last_funding_rate_long/precision}%")
    print(f"Last Funding Rate Short: {market.amm.last_funding_rate_short/precision}%")

    print(f"Oracle Price TWAP: ${oracle_twap/QUOTE_PRECISION:.2f}")

    live_mark_twap = calculate_live_mark_twap(
        market, oracle_price_data, mark_price, now
    )
    print(f"Live Mark TWAP: ${live_mark_twap/QUOTE_PRECISION:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
