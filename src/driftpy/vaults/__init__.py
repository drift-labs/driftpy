"""
Some simple helpers for interacting with the vaults program.

For a complete vaults SDK, please see https://github.com/drift-labs/drift-vaults
"""

from driftpy.vaults.helpers import (
    fetch_all_vault_depositors,
    filter_vault_depositors,
    get_all_vaults,
    get_depositor_info,
    get_vault_by_name,
    get_vault_depositors,
    get_vault_stats,
    get_vaults_program,
)
from driftpy.vaults.vault_client import VaultClient

__all__ = [
    "get_vaults_program",
    "get_all_vaults",
    "get_vault_by_name",
    "get_vault_depositors",
    "get_vault_stats",
    "get_depositor_info",
    "filter_vault_depositors",
    "fetch_all_vault_depositors",
    "VaultClient",
]
