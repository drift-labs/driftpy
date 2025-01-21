import asyncio
import os

from anchorpy.provider import Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient

from driftpy.accounts.get_accounts import get_spot_market_account
from driftpy.drift_client import DriftClient
from driftpy.math.spot_balance import (
    calculate_borrow_rate,
    calculate_deposit_rate,
    calculate_interest_rate,
    calculate_utilization,
)
from driftpy.math.spot_market import get_token_amount
from driftpy.types import SpotBalanceType


async def main():
    load_dotenv()
    url = os.getenv("RPC_URL")
    connection = AsyncClient(url)
    dc = DriftClient(connection, Wallet.dummy(), "mainnet")
    market = await get_spot_market_account(dc.program, 0)  # USDC
    if market is None:
        raise Exception("No market found")
    token_deposit_amount = get_token_amount(
        market.deposit_balance,
        market,
        SpotBalanceType.Deposit(),  # type: ignore
    )

    token_borrow_amount = get_token_amount(
        market.borrow_balance,
        market,
        SpotBalanceType.Borrow(),  # type: ignore
    )
    print(f"token_deposit_amount: {(token_deposit_amount/10**market.decimals):,.2f}")
    print(f"token_borrow_amount: {(token_borrow_amount/10**market.decimals):,.2f}")

    borrow_rate = calculate_borrow_rate(market)
    deposit_rate = calculate_deposit_rate(market)
    utilization = calculate_utilization(market)
    interest_rate = calculate_interest_rate(market)

    precision = 10000
    print(f"borrow_rate: {borrow_rate/precision:.2f}%")
    print(f"deposit_rate: {deposit_rate/precision:.2f}%")
    print(f"utilization: {utilization/precision:.2f}%")
    print(f"interest_rate: {interest_rate/precision:.2f}%")


if __name__ == "__main__":
    asyncio.run(main())
