import asyncio
import os

from anchorpy.provider import Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair

from driftpy.addresses import get_protected_maker_mode_config_public_key
from driftpy.drift_client import DriftClient
from driftpy.math.user_status import is_user_protected_maker

load_dotenv()


async def is_protected_maker():
    rpc = os.environ.get("RPC_TRITON")
    kp = Keypair.from_base58_string(os.environ.get("PRIVATE_KEY", ""))
    wallet = Wallet(kp)
    connection = AsyncClient(rpc)
    drift_client = DriftClient(
        connection=connection,
        wallet=wallet,
        env="mainnet",
    )
    await drift_client.subscribe()
    user = drift_client.get_user()
    print(user.get_open_orders())
    print(get_protected_maker_mode_config_public_key(drift_client.program_id))
    print(
        "Is user protected maker: ",
        is_user_protected_maker(user.get_user_account()),
    )
    print(await drift_client.update_user_protected_maker_orders(0, True))
    print(
        "Is user protected maker: ",
        is_user_protected_maker(user.get_user_account()),
    )
    await drift_client.unsubscribe()


if __name__ == "__main__":
    asyncio.run(is_protected_maker())
