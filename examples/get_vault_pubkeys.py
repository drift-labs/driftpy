import asyncio
import os

import dotenv
from solana.rpc.async_api import AsyncClient

from driftpy.constants.vaults import get_vaults_program

dotenv.load_dotenv()

connection = AsyncClient(os.getenv("RPC_URL"))


async def get_vaults():
    program = await get_vaults_program(connection)
    vaults = await program.account["Vault"].all()
    return vaults


async def main():
    vaults = await get_vaults()
    print(f"Found {len(vaults)} vault accounts")
    for vault in vaults:
        print(vault.account.pubkey)


if __name__ == "__main__":
    asyncio.run(main())
