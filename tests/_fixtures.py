import math
import pytest


import anchorpy
import pytest_asyncio
import solana.keypair
import solana.publickey

import driftpy.admin
import driftpy.constants.numeric_constants
import driftpy.setup.helpers

MANTISSA_SQRT_SCALE = int(math.sqrt(driftpy.constants.numeric_constants.PRICE_PRECISION))
AMM_INITIAL_QUOTE_ASSET_AMOUNT = int((5 * driftpy.constants.numeric_constants.AMM_RESERVE_PRECISION) * MANTISSA_SQRT_SCALE)
AMM_INITIAL_BASE_ASSET_AMOUNT = int((5 * driftpy.constants.numeric_constants.AMM_RESERVE_PRECISION) * MANTISSA_SQRT_SCALE)
PERIODICITY = 60 * 60  # 1 HOUR
USDC_AMOUNT = int(10 * driftpy.constants.numeric_constants.QUOTE_PRECISION)
MARKET_INDEX = 0

workspace = anchorpy.workspace_fixture(
    "../protocol-v2", build_cmd="anchor build --skip-lint", scope="session"
)

@pytest.fixture(scope="session")
def program(workspace: anchorpy.WorkspaceType) -> anchorpy.Program:
    """Create a Program instance."""
    return workspace["drift"]

@pytest_asyncio.fixture(scope="session")
async def clearing_house(program: anchorpy.Program, usdc_mint: solana.keypair.Keypair) -> driftpy.admin.Admin:
    admin = driftpy.admin.Admin(program)
    await admin.initialize(usdc_mint.public_key, admin_controls_prices=True)
    return admin 


@pytest_asyncio.fixture(scope="session")
async def usdc_mint(provider: anchorpy.Provider):
    return await driftpy.setup.helpers._create_mint(provider)


@pytest.fixture(scope="session")
def provider(program: anchorpy.Program) -> anchorpy.Provider:
    return program.provider

@pytest_asyncio.fixture(scope="session")
async def initialized_market(
    clearing_house: driftpy.admin.Admin, workspace: anchorpy.WorkspaceType
) -> solana.publickey.PublicKey:

    pyth_program = workspace["pyth"]

    sol_usd = await driftpy.setup.helpers.mock_oracle(pyth_program=pyth_program, price=1)

    await clearing_house.initialize_perp_market(
        sol_usd,
        AMM_INITIAL_BASE_ASSET_AMOUNT,
        AMM_INITIAL_QUOTE_ASSET_AMOUNT,
        PERIODICITY,
    )

    return sol_usd

@pytest_asyncio.fixture(scope="session")
async def initialized_spot_market(
    clearing_house: driftpy.admin.Admin, 
    usdc_mint: solana.keypair.Keypair,
): 
    await clearing_house.initialize_spot_market(
        usdc_mint.public_key 
    )


@pytest_asyncio.fixture(scope="session")
async def user_usdc_account(
    usdc_mint: solana.keypair.Keypair,
    provider: anchorpy.Provider,
):
    return await driftpy.setup.helpers._create_and_mint_user_usdc(
        usdc_mint, 
        provider, 
        USDC_AMOUNT * 2, 
        provider.wallet.public_key
    )