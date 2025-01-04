import asyncio
import os

from anchorpy import Provider, Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair

from driftpy.constants.numeric_constants import MARGIN_PRECISION
from driftpy.drift_client import AccountSubscriptionConfig, DriftClient

load_dotenv()


async def get_all_market_names():
    rpc = os.environ.get("MAINNET_RPC_ENDPOINT")
    kp = Keypair()  # random wallet
    wallet = Wallet(kp)
    connection = AsyncClient(rpc)
    provider = Provider(connection, wallet)
    drift_client = DriftClient(
        provider.connection,
        provider.wallet,
        "mainnet",
        account_subscription=AccountSubscriptionConfig("cached"),
    )
    await drift_client.subscribe()
    all_perps_markets = await drift_client.program.account["PerpMarket"].all()
    sorted_all_perps_markets = sorted(
        all_perps_markets, key=lambda x: x.account.market_index
    )
    result_perp = [
        bytes(x.account.name).decode("utf-8").strip() for x in sorted_all_perps_markets
    ]
    print("Perp Markets:")
    for index, market in enumerate(result_perp):
        max_leverage = get_perp_market_max_leverage(drift_client, index)
        print(f"{market} - {max_leverage}")

    result = result_perp + result_spot[1:]
    return result


def get_perp_market_max_leverage(drift_client, market_index: int) -> float:
    market = drift_client.get_perp_market_account(market_index)
    standard_max_leverage = MARGIN_PRECISION / market.margin_ratio_initial

    high_leverage = (
        MARGIN_PRECISION / market.high_leverage_margin_ratio_initial
        if market.high_leverage_margin_ratio_initial > 0
        else 0
    )
    max_leverage = max(standard_max_leverage, high_leverage)
    return max_leverage


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    answer = loop.run_until_complete(get_all_market_names())
    print(answer)
