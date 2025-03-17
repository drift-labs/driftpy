import asyncio
import os

import dotenv
from anchorpy.provider import Wallet
from solana.rpc.async_api import AsyncClient

from driftpy.accounts import get_spot_market_account
from driftpy.drift_client import DriftClient
from driftpy.vaults import (
    fetch_all_vault_depositors,
    filter_vault_depositors,
    get_all_vaults,
    get_vault_stats,
    get_vaults_program,
)

dotenv.load_dotenv()

connection = AsyncClient(os.getenv("RPC_TRITON"))


async def analyze_vaults():
    print("Fetching vault data...")
    vaults_program = await get_vaults_program(connection)
    vaults = await get_all_vaults(vaults_program)
    print(f"Found {len(vaults)} vault accounts")

    client = DriftClient(connection, wallet=Wallet.dummy())
    all_depositors = await fetch_all_vault_depositors(vaults_program)
    print(f"Found {len(all_depositors):,.2f} depositors")

    vault_stats = await get_vault_stats(
        vaults_program, [vault.account.pubkey for vault in vaults]
    )

    spot_to_decimals = {}
    for vault in vault_stats:
        if vault["spot_market_index"] not in spot_to_decimals:
            spot_market = await get_spot_market_account(
                client.program, vault["spot_market_index"]
            )
            spot_to_decimals[vault["spot_market_index"]] = spot_market.decimals

    for vault in vault_stats:
        decimals = spot_to_decimals[vault["spot_market_index"]]
        vault["true_net_deposits"] = vault["net_deposits"] / (10**decimals)
        vault["true_total_deposits"] = vault["total_deposits"] / (10**decimals)
        vault["true_total_withdraws"] = vault["total_withdraws"] / (10**decimals)

    for vault in vault_stats:
        depositors = await filter_vault_depositors(all_depositors, vault["pubkey"])
        vault["depositor_count"] = len(depositors)

    sorted_by_deposits = sorted(
        vault_stats, key=lambda x: x["true_net_deposits"], reverse=True
    )
    sorted_by_users = sorted(
        vault_stats, key=lambda x: x["depositor_count"], reverse=True
    )

    # Output top 5 by deposits
    print("\n----- Top 5 Vaults by Net Deposits -----")
    for i, vault in enumerate(sorted_by_deposits[:5], 1):
        print(
            f"{i}. {vault['name']}: {vault['true_net_deposits']:,.2f} (Users: {vault['depositor_count']})"
        )

    # Output top 5 by user count
    print("\n----- Top 5 Vaults by User Count -----")
    for i, vault in enumerate(sorted_by_users[:5], 1):
        print(
            f"{i}. {vault['name']}: {vault['depositor_count']} users (Deposits: {vault['true_net_deposits']:,.2f})"
        )

    # Calculate interesting metrics
    total_deposits = sum(vault["true_net_deposits"] for vault in vault_stats)
    total_users = sum(vault["depositor_count"] for vault in vault_stats)

    print("\n----- Overall Statistics -----")
    print(f"Total Vaults: {len(vaults)}")
    print(f"Total Deposited Value: {total_deposits:,.2f}")
    print(f"Total Unique Depositors: {total_users}")
    print(f"Average Deposit per Vault: {total_deposits/len(vaults):,.2f}")

    # Detailed look at the largest vault
    largest_vault = sorted_by_deposits[0]
    print(f"\n----- Details for Largest Vault: {largest_vault['name']} -----")
    print(f"Net Deposits: {largest_vault['true_net_deposits']:,.2f}")
    print(f"Total Depositors: {largest_vault['depositor_count']}")

    # Get depositors for largest vault
    depositors = await filter_vault_depositors(all_depositors, largest_vault["pubkey"])

    # Calculate average deposit per user in largest vault
    if depositors:
        print(
            f"Average Deposit per User: {largest_vault['true_net_deposits']/largest_vault['depositor_count']:,.2f}"
        )

        # Quick analysis of depositor distribution
        depositor_shares = [getattr(d, "vault_shares", 0) for d in depositors]
        if depositor_shares:
            max_shares = max(depositor_shares)
            min_shares = min(depositor_shares)
            print(f"Largest Depositor Share: {max_shares}")
            print(f"Smallest Depositor Share: {min_shares}")
            print(
                f"Ratio between largest and smallest: {max_shares/min_shares if min_shares else 'N/A'}"
            )


if __name__ == "__main__":
    asyncio.run(analyze_vaults())
