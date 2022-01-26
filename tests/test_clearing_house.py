from math import sqrt
from pytest import fixture, mark
from pytest_asyncio import fixture as async_fixture
from solana.keypair import Keypair
from solana.publickey import PublicKey
from anchorpy import Program, Provider, WorkspaceType

from driftpy.admin import Admin
from driftpy.constants.markets import MARKETS
from driftpy.constants.numeric_constants import MARK_PRICE_PRECISION
from driftpy.types import StateAccount
from .helpers import mock_oracle

MANTISSA_SQRT_SCALE = int(sqrt(MARK_PRICE_PRECISION))
AMM_INITIAL_QUOTE_ASSET_AMOUNT = int((5 * 10 ** 13) * MANTISSA_SQRT_SCALE)
AMM_INITIAL_BASE_ASSET_AMOUNT = int((5 * 10 ** 13) * MANTISSA_SQRT_SCALE)
PERIODICITY = 60 * 60  # 1 HOUR


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

    markets_account = await clearing_house.get_markets_account()
    assert len(markets_account.markets) == 64

    funding_rate_history = await clearing_house.get_funding_payment_history_account()
    assert funding_rate_history.head == 0
    assert len(funding_rate_history.funding_payment_records) == 1024

    trade_history_account = await clearing_house.get_trade_history_account()
    assert trade_history_account.head == 0
    assert len(trade_history_account.trade_records) == 1024


@async_fixture(scope="module")
async def initialized_market(
    clearing_house: Admin, workspace: WorkspaceType
) -> PublicKey:
    pyth_program = workspace["pyth"]
    sol_usd = await mock_oracle(pyth_program=pyth_program, price=1)

    await clearing_house.initialize_market(
        MARKETS[0].market_index,
        sol_usd,
        AMM_INITIAL_BASE_ASSET_AMOUNT,
        AMM_INITIAL_QUOTE_ASSET_AMOUNT,
        PERIODICITY,
    )
    return sol_usd


@mark.asyncio
async def test_initialized_market(
    initialized_market: PublicKey, clearing_house: Admin
) -> None:
    sol_usd = initialized_market
    markets_account = await clearing_house.get_markets_account()

    market_data = markets_account.markets[0]
    assert market_data.initialized
    assert market_data.base_asset_amount == 0
    assert market_data.open_interest == 0

    amm_data = market_data.amm
    assert amm_data.oracle == sol_usd
    assert amm_data.base_asset_reserve == AMM_INITIAL_BASE_ASSET_AMOUNT
    assert amm_data.quote_asset_reserve == AMM_INITIAL_QUOTE_ASSET_AMOUNT
    assert amm_data.cumulative_funding_rate_long == 0
    assert amm_data.cumulative_funding_rate_short == 0
    assert amm_data.funding_period == PERIODICITY
    assert amm_data.last_funding_rate == 0
    assert amm_data.last_funding_rate_ts != 0
