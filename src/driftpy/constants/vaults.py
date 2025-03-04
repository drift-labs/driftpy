"""
This is just a helper to get the vaults program as an anchorpy Program object

For an actual vaults usage sdk, please see https://github.com/drift-labs/drift-vaults
"""

from pathlib import Path

from anchorpy import Idl, Program
from anchorpy.provider import Provider, Wallet
from solana.rpc.async_api import AsyncClient

import driftpy
from driftpy.constants.config import VAULT_PROGRAM_ID


async def get_vaults_program(connection: AsyncClient) -> Program:
    """
    Get the vaults program as an anchorpy Program object
    """
    file = Path(str(driftpy.__path__[0]) + "/idl/drift_vaults.json")
    IDL = Idl.from_json(file.read_text())
    provider = Provider(connection=connection, wallet=Wallet.dummy())
    program = Program(idl=IDL, provider=provider, program_id=VAULT_PROGRAM_ID)

    return program
