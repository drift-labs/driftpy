import asyncio
import os

from anchorpy.provider import Provider, Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solders.keypair import Keypair

from driftpy.drift_client import AccountSubscriptionConfig, DriftClient
from driftpy.types import GrpcConfig

load_dotenv()

RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"

CLEAR_SCREEN = "\033c"


async def watch_drift_markets():
    rpc_fqdn = os.environ.get("RPC_FQDN")
    x_token = os.environ.get("X_TOKEN")
    private_key = os.environ.get("PRIVATE_KEY")
    rpc_url = os.environ.get("RPC_TRITON")

    if not (rpc_fqdn and x_token and private_key and rpc_url):
        raise ValueError("RPC_FQDN, X_TOKEN, PRIVATE_KEY, and RPC_TRITON must be set")

    wallet = Wallet(Keypair.from_base58_string(private_key))
    connection = AsyncClient(rpc_url)
    provider = Provider(connection, wallet)

    drift_client = DriftClient(
        provider.connection,
        provider.wallet,
        "mainnet",
        account_subscription=AccountSubscriptionConfig(
            "grpc",
            grpc_config=GrpcConfig(
                endpoint=rpc_fqdn,
                token=x_token,
                commitment=Commitment("confirmed"),
            ),
        ),
    )

    await drift_client.subscribe()
    print("Subscribed via gRPC. Listening for market updates...")

    previous_prices = {}

    while True:
        print(CLEAR_SCREEN, end="")

        perp_markets = drift_client.get_perp_market_accounts()

        if not perp_markets:
            print(f"{RED}No perp markets found (yet){RESET}")
        else:
            print("Drift Perp Markets (gRPC subscription)\n")
            perp_markets.sort(key=lambda x: x.market_index)
            for market in perp_markets[:20]:
                market_index = market.market_index
                last_price = market.amm.historical_oracle_data.last_oracle_price / 1e6

                if market_index in previous_prices:
                    old_price = previous_prices[market_index]
                    if last_price > old_price:
                        color = GREEN
                    elif last_price < old_price:
                        color = RED
                    else:
                        color = RESET
                else:
                    color = RESET

                print(
                    f"Market Index: {market_index} | "
                    f"Price: {color}${last_price:.4f}{RESET}"
                )

                previous_prices[market_index] = last_price

        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(watch_drift_markets())
