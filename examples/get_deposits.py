import asyncio
import os

from anchorpy.provider import Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.constants.numeric_constants import SPOT_BALANCE_PRECISION
from driftpy.drift_client import DriftClient
from driftpy.market_map.market_map import MarketMap
from driftpy.market_map.market_map_config import MarketMapConfig
from driftpy.market_map.market_map_config import (
    WebsocketConfig as MarketMapWebsocketConfig,
)
from driftpy.pickle.vat import Vat
from driftpy.types import MarketType, is_variant
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import UserMapConfig, UserStatsMapConfig
from driftpy.user_map.user_map_config import (
    WebsocketConfig as UserMapWebsocketConfig,
)
from driftpy.user_map.userstats_map import UserStatsMap

load_dotenv()


def get_deposits_by_authority(vat: Vat, market_index: int):
    deposits = {}

    for user in vat.users.values():
        for position in user.get_user_account().spot_positions:
            if (
                position.market_index == market_index
                and position.scaled_balance > 0
                and not is_variant(position.balance_type, "Borrow")
            ):
                authority = user.user_public_key
                balance = position.scaled_balance / SPOT_BALANCE_PRECISION

                if authority in deposits:
                    deposits[authority] += balance
                else:
                    deposits[authority] = balance

    return {
        "deposits": [
            {"authority": authority, "balance": balance}
            for authority, balance in sorted(
                deposits.items(), key=lambda x: x[1], reverse=True
            )
        ]
    }


async def main():
    rpc_url = os.getenv("MAINNET_RPC_ENDPOINT")
    if not rpc_url:
        raise ValueError("MAINNET_RPC_ENDPOINT is not set")

    connection = AsyncClient(rpc_url)
    wallet = Wallet.dummy()
    dc = DriftClient(
        connection,
        wallet,
        "mainnet",
        account_subscription=AccountSubscriptionConfig("cached"),
    )
    perp_map = MarketMap(
        MarketMapConfig(
            dc.program,
            MarketType.Perp(),  # type: ignore
            MarketMapWebsocketConfig(),
            dc.connection,
        )
    )
    spot_map = MarketMap(
        MarketMapConfig(
            dc.program,
            MarketType.Spot(),  # type: ignore
            MarketMapWebsocketConfig(),
            dc.connection,
        )
    )
    user_map = UserMap(UserMapConfig(dc, UserMapWebsocketConfig()))
    stats_map = UserStatsMap(UserStatsMapConfig(dc))
    await asyncio.gather(
        asyncio.create_task(spot_map.subscribe()),
        asyncio.create_task(perp_map.subscribe()),
        asyncio.create_task(user_map.subscribe()),
        asyncio.create_task(stats_map.subscribe()),
    )
    print("Subscribed to Drift Client")
    await user_map.sync()
    print("Synced User Map")

    vat = Vat(
        dc,
        user_map,
        stats_map,
        spot_map,
        perp_map,
    )
    deposits = get_deposits_by_authority(vat, 0)
    return deposits


if __name__ == "__main__":
    deposits = asyncio.run(main())
    print(deposits)
