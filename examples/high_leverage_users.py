import asyncio
import os

from anchorpy import Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient

from driftpy.drift_client import DriftClient
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import UserMapConfig
from driftpy.user_map.user_map_config import (
    WebsocketConfig as UserMapWebsocketConfig,
)


async def main():
    load_dotenv()
    url = os.getenv("RPC_URL")
    connection = AsyncClient(url)
    dc = DriftClient(
        connection,
        Wallet.dummy(),
        "mainnet",
    )
    await dc.subscribe()
    user = UserMap(UserMapConfig(dc, UserMapWebsocketConfig()))
    await user.subscribe()

    high_leverage_users = []
    keys = []
    for key, user in user.user_map.items():
        if user.is_high_leverage_mode():
            high_leverage_users.append(user)
            keys.append(key)
    return high_leverage_users, keys


if __name__ == "__main__":
    high_leverage_users, keys = asyncio.run(main())
    keys.sort()
    print(f"Number of high leverage users: {len(keys)}")
    # with open("high_leverage_users.txt", "w") as f:
    #     for key in keys:
    #         f.write(f"{key}\n")
