import asyncio
import os

from anchorpy.provider import Provider, Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient

from driftpy.drift_client import DriftClient
from driftpy.keypair import load_keypair
from driftpy.types import TxParams

LAMPORTS_PER_SOL = 10**9


load_dotenv()


async def make_spot_trade():
    rpc = os.environ.get("RPC_TRITON")
    secret = os.environ.get("PRIVATE_KEY")
    kp = load_keypair(secret)
    wallet = Wallet(kp)
    print(f"Using wallet: {wallet.public_key}")

    connection = AsyncClient(rpc)
    provider = Provider(connection, wallet)
    drift_client = DriftClient(
        provider.connection,
        provider.wallet,
        env="mainnet",
        tx_params=TxParams(compute_units_price=85_000, compute_units=1_400_000),
    )
    await drift_client.subscribe()

    print("Drift client subscribed")

    amount = int(0.4 * LAMPORTS_PER_SOL)

    print("Depositing 0.4")
    await drift_client.deposit(
        amount=amount,
        spot_market_index=1,
        user_token_account=drift_client.wallet.public_key,
    )
    print("Deposited 0.4")

    print("Withdrawing 0.4")
    await drift_client.withdraw(
        amount=amount,
        market_index=1,
        user_token_account=drift_client.wallet.public_key,
    )
    print("Withdrew 0.4")


if __name__ == "__main__":
    asyncio.run(make_spot_trade())
