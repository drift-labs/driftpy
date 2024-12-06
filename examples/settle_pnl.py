import argparse
import asyncio
import os

from anchorpy import Wallet
from dotenv import load_dotenv
from driftpy.drift_client import DriftClient
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey


load_dotenv()


async def setup_drift_client() -> DriftClient:
    connection = AsyncClient(os.getenv("RPC_URL"))
    kp = Keypair.from_base58_string(os.getenv("PRIVATE_KEY"))
    wallet = Wallet(kp)
    drift_client = DriftClient(connection=connection, wallet=wallet, env="mainnet")
    await drift_client.subscribe()
    await drift_client.account_subscriber.fetch()
    print("drift_client subscribe done")
    return drift_client


async def settle_pnl_once(
    drift_client: DriftClient, user_public_key: Pubkey, market_index: int
):
    user = drift_client.get_user()
    account_info = user.get_user_account_and_slot().data
    tx_hash = await drift_client.settle_pnl(user_public_key, account_info, market_index)
    print(f"Settled PNL for market {market_index}, tx: {tx_hash}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subaccount_id", type=int, required=True)
    parser.add_argument("--market_index", type=int, required=True)
    args = parser.parse_args()

    try:
        drift_client = await setup_drift_client()
        user_public_key = drift_client.get_user_account_public_key(args.subaccount_id)
        await asyncio.wait_for(
            settle_pnl_once(drift_client, user_public_key, args.market_index),
            timeout=540,
        )
    except:
        raise


if __name__ == "__main__":
    asyncio.run(main())
