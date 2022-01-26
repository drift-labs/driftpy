from pytest import fixture, mark
from pytest_asyncio import fixture as async_fixture
from solana.publickey import PublicKey
from solana.keypair import Keypair
from anchorpy import Program, Provider, WorkspaceType

from driftpy.admin import Admin
from driftpy.types import StateAccount


@fixture(scope="module")
def program(workspace: WorkspaceType) -> Program:
    return workspace["clearing_house"]


@async_fixture(scope="module")
async def clearing_house(program: Program, usdc_mint: Keypair) -> Admin:
    await Admin.initialize(program, usdc_mint.public_key, admin_controls_prices=True)
    return await Admin.from_(program.program_id, program.provider)


@async_fixture(scope="module")
async def state(clearing_house: Admin) -> StateAccount:
    return await clearing_house.get_state_account()


@mark.asyncio
async def test_state(state: StateAccount, provider: Provider, clearing_house: Admin):
    assert state.admin == provider.wallet.public_key
    (
        expected_collateral_account_authority,
        expected_collateral_account_nonce,
    ) = clearing_house._find_program_address(
        [bytes(state.collateral_vault)],
    )

    assert state.collateral_vault_authority == expected_collateral_account_authority

    assert state.collateral_vault_nonce == expected_collateral_account_nonce
    (
        expected_insurance_account_authority,
        expected_insurance_account_nonce,
    ) = clearing_house._find_program_address(
        [bytes(state.insurance_vault)],
    )
    assert state.insurance_vault_authority == expected_insurance_account_authority
    assert state.insurance_vault_nonce == expected_insurance_account_nonce

    markets_account = clearing_house.get_markets_account()
    assert markets_account.markets.length == 64

    funding_rate_history = clearing_house.get_funding_payment_history_account()
    assert funding_rate_history.head.toNumber() == 0
    assert funding_rate_history.funding_payment_records.length == 1024

    trade_history_account = clearing_house.get_trade_history_account()
    assert trade_history_account.head.toNumber() == 0
    assert trade_history_account.trade_records.length == 1024
