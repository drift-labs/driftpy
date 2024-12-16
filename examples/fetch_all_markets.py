import asyncio
import os

from anchorpy.provider import Provider, Wallet
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair

from driftpy.drift_client import AccountSubscriptionConfig, DriftClient


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
        account_subscription=AccountSubscriptionConfig("websocket"),
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
    for market in result_perp:
        print(market)

    all_spot_markets = await drift_client.program.account["SpotMarket"].all()
    sorted_all_spot_markets = sorted(
        all_spot_markets, key=lambda x: x.account.market_index
    )
    result_spot = [
        bytes(x.account.name).decode("utf-8").strip() for x in sorted_all_spot_markets
    ]
    print("\n\nSpot Markets:")
    for market in result_spot:
        print(market)

    result = result_perp + result_spot[1:]

    print("Here are some prices:")
    print(drift_client.get_oracle_price_data_for_perp_market(0))
    print(drift_client.get_oracle_price_data_for_spot_market(0))
    await drift_client.unsubscribe()
    return result


if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        answer = loop.run_until_complete(get_all_market_names())
        print(answer)
    finally:
        # Clean up pending tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()

        # Run loop until tasks complete/cancel
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()
