import asyncio
import os

from anchorpy import Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient

from driftpy.addresses import get_protected_maker_mode_config_public_key
from driftpy.drift_client import DriftClient
from driftpy.math.user_status import is_user_protected_maker
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import UserMapConfig
from driftpy.user_map.user_map_config import (
    WebsocketConfig as UserMapWebsocketConfig,
)


async def main():
    load_dotenv()
    url = os.getenv("RPC_TRITON")
    connection = AsyncClient(url)
    dc = DriftClient(
        connection,
        Wallet.dummy(),
        "mainnet",
    )
    await dc.subscribe()
    user = UserMap(UserMapConfig(dc, UserMapWebsocketConfig(), include_idle=True))
    await user.subscribe()

    pmm_users = []
    keys = []
    print(get_protected_maker_mode_config_public_key(dc.program_id))
    for key, user in user.user_map.items():
        if is_user_protected_maker(user.get_user_account()):
            pmm_users.append(user)
            keys.append(key)

    return pmm_users, keys


if __name__ == "__main__":
    pmm_users, keys = asyncio.run(main())
    keys.sort()
    print(f"Number of protected maker users: {len(keys)}")
