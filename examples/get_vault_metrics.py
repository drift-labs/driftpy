import asyncio
import os

import dotenv
from solana.rpc.async_api import AsyncClient

from driftpy.vaults import VaultClient

dotenv.load_dotenv()

connection = AsyncClient(os.getenv("RPC_TRITON"))


def format_vault_summary(analytics, top_n=5):
    """Format vault data for readable output"""
    output = []
    output.append(f"Total Vaults: {analytics['total_vaults']}")
    output.append(f"Total Value Locked: {analytics['total_deposits']:,.2f}")
    output.append(f"Total Unique Depositors: {analytics['total_depositors']}")

    output.append("\n----- Top Vaults by Deposits -----")
    for i, vault in enumerate(analytics["top_by_deposits"][:top_n], 1):
        output.append(f"{i}. {vault['name']}: {vault['true_net_deposits']:,.2f}")

    output.append("\n----- Top Vaults by Users -----")
    for i, vault in enumerate(analytics["top_by_users"][:top_n], 1):
        output.append(f"{i}. {vault['name']}: {vault['depositor_count']} users")

    return "\n".join(output)


async def main():
    vault_client = await VaultClient(connection).initialize()
    print("Got vault client...")
    analytics = await vault_client.calculate_analytics()
    print("Got analytics...")
    depositors = await vault_client.get_all_depositors()
    print(f"Got {len(depositors)} depositors...")
    print("Top 5 depositors:")
    for i, dep in enumerate(depositors[:5], 1):
        print(f"{i}. {dep}")

    print(format_vault_summary(analytics))
    drift_boost = await vault_client.get_vault_by_name("SOL-NL-Neutral-Trade")

    if drift_boost:
        depositors = await vault_client.get_vault_depositors_with_stats(
            drift_boost.account.pubkey
        )
        print("\nTop 5 depositors:")
        for i, dep in enumerate(depositors[:5], 1):
            print(
                f"{i}. {dep['pubkey']}: {dep['shares']}, {dep['share_percentage']:.2f}%"
            )


if __name__ == "__main__":
    asyncio.run(main())
