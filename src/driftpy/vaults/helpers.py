"""
Helper functions for interacting with the Drift Vaults program.

This module provides utilities for querying vault information, depositors,
and other vault-related data.

Python functions provided here are for basic usage.
For a complete vaults SDK, please see https://github.com/drift-labs/drift-vaults
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, Union

from anchorpy import Idl, Program
from anchorpy.provider import Provider, Wallet
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

import driftpy
from driftpy.constants.config import VAULT_PROGRAM_ID


class WithdrawRequest(TypedDict):
    shares: int
    value: int
    ts: int


class VaultDepositor(TypedDict):
    vault: Pubkey
    pubkey: Pubkey
    authority: Pubkey
    vault_shares: int
    last_withdraw_request: WithdrawRequest
    last_valid_ts: int
    net_deposits: int
    total_deposits: int
    total_withdraws: int
    cumulative_profit_share_amount: int
    profit_share_fee_paid: int
    vault_shares_base: int
    last_fuel_update_ts: int
    cumulative_fuel_per_share_amount: int
    fuel_amount: int
    padding: List[int]


class TokenizedVaultDepositor(TypedDict):
    vault: Pubkey
    pubkey: Pubkey
    mint: Pubkey
    vault_shares: int


DepositorData = Dict[str, List[Union[VaultDepositor, TokenizedVaultDepositor]]]
DepositorList = List[Union[VaultDepositor, TokenizedVaultDepositor]]


async def get_vaults_program(connection: AsyncClient) -> Program:
    """
    Get the vaults program as an anchorpy Program object
    """
    file = Path(str(driftpy.__path__[0]) + "/idl/drift_vaults.json")
    IDL = Idl.from_json(file.read_text())
    provider = Provider(connection=connection, wallet=Wallet.dummy())
    program = Program(idl=IDL, provider=provider, program_id=VAULT_PROGRAM_ID)

    return program


async def get_all_vaults(program: Program) -> List[Dict[str, Any]]:
    """
    Get all vaults from the program

    Args:
        program: The vaults program

    Returns:
        List of vault accounts with their data
    """
    vaults = await program.account["Vault"].all()
    return vaults


async def get_vault_by_name(
    program: Program, name: str, case_sensitive: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Get a vault by its name

    Args:
        program: The vaults program
        name: The name of the vault
        case_sensitive: Whether to match the vault name case-sensitively

    Returns:
        The vault account with its data if found, None otherwise
    """
    vaults = await get_all_vaults(program)

    for vault in vaults:
        vault_name = bytes(vault.account.name).decode("utf-8").rstrip("\x00")
        if case_sensitive:
            if vault_name == name:
                return vault
        else:
            if vault_name.lower() == name.lower():
                return vault

    return None


async def fetch_all_vault_depositors(program: Program) -> DepositorData:
    """
    Fetch all vault depositors from the program

    Args:
        program: The vaults program

    Returns:
        Dictionary with 'regular' and 'tokenized' depositor lists
    """
    regular_depositors = []
    tokenized_depositors = []

    try:
        regular_depositors = await program.account["VaultDepositor"].all()
    except Exception as e:
        print(f"Error fetching regular depositors: {e}")

    try:
        tokenized_depositors = await program.account["TokenizedVaultDepositor"].all()
    except Exception as e:
        print(f"Error fetching tokenized depositors: {e}")

    return {
        "regular": [
            regular_depositor.account for regular_depositor in regular_depositors
        ],
        "tokenized": [
            tokenized_depositor.account for tokenized_depositor in tokenized_depositors
        ],
    }


async def filter_vault_depositors(
    depositors_data: List[VaultDepositor], vault_pubkey: str | Pubkey
) -> DepositorList:
    """
    Filter depositors for a specific vault from pre-fetched depositor data

    Args:
        depositors_data: Dictionary with 'regular' and 'tokenized' depositor lists
        vault_pubkey: The public key of the vault (can be string or Pubkey)

    Returns:
        List of vault depositor accounts for the specified vault
    """
    if isinstance(vault_pubkey, str):
        vault_pubkey = Pubkey.from_string(vault_pubkey)

    regular_depositors = [
        depositor
        for depositor in depositors_data
        if hasattr(depositor, "vault") and depositor.vault == vault_pubkey
    ]

    return regular_depositors


async def get_vault_depositors(
    program: Program, vault_pubkey: str | Pubkey
) -> DepositorList:
    """
    Get all depositors for a specific vault

    Args:
        program: The vaults program
        vault_pubkey: The public key of the vault (can be string or Pubkey)

    Returns:
        List of vault depositor accounts with their data
    """
    depositors_data = await fetch_all_vault_depositors(program)
    return await filter_vault_depositors(depositors_data, vault_pubkey)


async def get_vault_stats(
    program: Program,
    vault_pubkeys: List[Pubkey],
    include_depositors: bool = False,
) -> Dict[str, Any]:
    """
    Get detailed statistics for a vault including total deposits, shares, etc.

    Args:
        program: The vaults program
        vault_pubkeys: The public keys of the vaults
        include_depositors: Whether to include depositors in the stats

    Returns:
        Dictionary with vault statistics
    """
    vaults = await program.account["Vault"].fetch_multiple(vault_pubkeys)
    depositors_data = await fetch_all_vault_depositors(program)
    vault_stats = []
    for vault in vaults:
        vault_stat = {
            "name": bytes(vault.name).decode("utf-8").rstrip("\x00"),
            "pubkey": str(vault.pubkey),
            "manager": str(vault.manager),
            "total_shares": int(vault.total_shares),
            "user_shares": int(vault.user_shares),
            "total_deposits": vault.total_deposits,
            "total_withdraws": vault.total_withdraws,
            "net_deposits": vault.net_deposits,
            "management_fee": vault.management_fee,
            "profit_share": vault.profit_share,
            "spot_market_index": vault.spot_market_index,
        }
        if include_depositors:
            vault_stat["depositors"] = await filter_vault_depositors(
                depositors_data, vault.pubkey
            )

        vault_stats.append(vault_stat)

    return vault_stats


async def get_depositor_info(
    program: Program, vault_pubkey: Pubkey, depositor_pubkey: Pubkey
) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific depositor in a vault

    Args:
        program: The vaults program
        vault_pubkey: The public key of the vault
        depositor_pubkey: The public key of the depositor

    Returns:
        Dictionary with depositor information if found, None otherwise
    """
    try:
        depositor = await program.account["VaultDepositor"].fetch(depositor_pubkey)
        depositor_type = "VaultDepositor"
    except Exception as e:
        print(e)
        try:
            depositor = await program.account["TokenizedVaultDepositor"].fetch(
                depositor_pubkey
            )
            depositor_type = "TokenizedVaultDepositor"
        except Exception as e:
            print(e)
            return None

    vault = await program.account["Vault"].fetch(vault_pubkey)

    share_percentage = 0
    if int(vault.totalShares) > 0:
        share_percentage = (int(depositor.vaultShares) / int(vault.totalShares)) * 100

    result = {
        "pubkey": str(depositor_pubkey),
        "vault": str(vault_pubkey),
        "type": depositor_type,
        "shares": int(depositor.vaultShares),
        "share_percentage": share_percentage,
        "net_deposits": depositor.netDeposits
        if hasattr(depositor, "netDeposits")
        else None,
        "total_deposits": depositor.totalDeposits
        if hasattr(depositor, "totalDeposits")
        else None,
        "total_withdraws": depositor.totalWithdraws
        if hasattr(depositor, "totalWithdraws")
        else None,
    }

    if hasattr(depositor, "authority"):
        result["authority"] = str(depositor.authority)

    if hasattr(depositor, "mint"):
        result["mint"] = str(depositor.mint)

    return result
