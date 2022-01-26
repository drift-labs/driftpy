import asyncio
from pytest import fixture
from pytest_asyncio import fixture as async_fixture
from anchorpy import Provider, WorkspaceType, workspace_fixture
from solana.keypair import Keypair
from solana.transaction import Transaction
from solana.system_program import create_account, CreateAccountParams
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token._layouts import MINT_LAYOUT
from spl.token.async_client import AsyncToken
from spl.token.instructions import initialize_mint, InitializeMintParams


@fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()  # noqa: DAR301
    yield loop
    loop.close()


workspace = workspace_fixture("./drift-core", scope="session")


@fixture(scope="session")
def provider(workspace: WorkspaceType) -> Provider:
    return workspace["clearing_house"].provider


@async_fixture(scope="session")
async def usdc_mint(provider: Provider) -> Keypair:
    fake_usdc_mint = Keypair()
    params = CreateAccountParams(
        from_pubkey=provider.wallet.public_key,
        new_account_pubkey=fake_usdc_mint.public_key,
        lamports=await AsyncToken.get_min_balance_rent_for_exempt_for_mint(
            provider.connection
        ),
        space=MINT_LAYOUT.sizeof(),
        program_id=TOKEN_PROGRAM_ID,
    )
    create_usdc_mint_account_ix = create_account(params)
    init_collateral_mint_ix = initialize_mint(
        InitializeMintParams(
            decimals=6,
            program_id=TOKEN_PROGRAM_ID,
            mint=fake_usdc_mint.public_key,
            mint_authority=provider.wallet.public_key,
            freeze_authority=None,
        )
    )
    fake_usdc_tx = Transaction().add(
        create_usdc_mint_account_ix, init_collateral_mint_ix
    )
    await provider.send(fake_usdc_tx, [fake_usdc_mint])
    return fake_usdc_mint
