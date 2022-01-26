from math import sqrt
from pytest import fixture, mark
from pytest_asyncio import fixture as async_fixture
from solana.keypair import Keypair
from solana.publickey import PublicKey
from solana.transaction import Transaction
from solana.system_program import create_account, CreateAccountParams
from spl.token.async_client import AsyncToken
from spl.token._layouts import ACCOUNT_LAYOUT
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import (
    initialize_account,
    InitializeAccountParams,
    mint_to,
    MintToParams,
)
from anchorpy import Program, Provider, WorkspaceType
from anchorpy.utils.token import get_token_account

from driftpy.admin import Admin
from driftpy.constants.markets import MARKETS
from driftpy.constants.numeric_constants import MARK_PRICE_PRECISION
from driftpy.types import DepositDirection, StateAccount, User, UserPositions
from .helpers import mock_oracle

MANTISSA_SQRT_SCALE = int(sqrt(MARK_PRICE_PRECISION))
AMM_INITIAL_QUOTE_ASSET_AMOUNT = int((5 * 10 ** 13) * MANTISSA_SQRT_SCALE)
AMM_INITIAL_BASE_ASSET_AMOUNT = int((5 * 10 ** 13) * MANTISSA_SQRT_SCALE)
PERIODICITY = 60 * 60  # 1 HOUR
USDC_AMOUNT = int(10 * 10 ** 6)


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


@async_fixture(scope="module")
async def user_usdc_account(
    usdc_mint: Keypair,
    provider: Provider,
) -> Keypair:
    account = Keypair()
    fake_usdc_tx = Transaction()

    owner = provider.wallet.public_key

    create_usdc_token_account_ix = create_account(
        CreateAccountParams(
            from_pubkey=provider.wallet.public_key,
            new_account_pubkey=account.public_key,
            lamports=await AsyncToken.get_min_balance_rent_for_exempt_for_account(
                provider.connection
            ),
            space=ACCOUNT_LAYOUT.sizeof(),
            program_id=TOKEN_PROGRAM_ID,
        )
    )
    fake_usdc_tx.add(create_usdc_token_account_ix)

    init_usdc_token_account_ix = initialize_account(
        InitializeAccountParams(
            program_id=TOKEN_PROGRAM_ID,
            account=account.public_key,
            mint=usdc_mint.public_key,
            owner=owner,
        )
    )
    fake_usdc_tx.add(init_usdc_token_account_ix)

    mint_to_user_account_tx = mint_to(
        MintToParams(
            program_id=TOKEN_PROGRAM_ID,
            mint=usdc_mint.public_key,
            dest=account.public_key,
            mint_authority=provider.wallet.public_key,
            signers=[],
            amount=USDC_AMOUNT,
        )
    )
    fake_usdc_tx.add(mint_to_user_account_tx)

    await provider.send(fake_usdc_tx, [provider.wallet.payer, account])
    return account


@async_fixture(scope="module")
async def initialized_user_account_with_deposit(
    clearing_house: Admin, user_usdc_account: Keypair
) -> PublicKey:
    (
        _,
        user_account_public_key,
    ) = await clearing_house.initialize_user_account_and_deposit_collateral(
        USDC_AMOUNT, user_usdc_account.public_key
    )
    return user_account_public_key


@mark.asyncio
async def test_initialize_user_account_with_collateral(
    clearing_house: Admin,
    initialized_user_account_with_deposit: PublicKey,
    provider: Provider,
) -> None:
    user_account_public_key = initialized_user_account_with_deposit
    user: User = await clearing_house.program.account["User"].fetch(
        user_account_public_key
    )
    assert user.authority == provider.wallet.public_key
    assert user.collateral == USDC_AMOUNT
    assert user.cumulative_deposits == USDC_AMOUNT

    # Check that clearing house collateral account has proper collateral
    clearing_house_state = await clearing_house.get_state_account()
    clearing_house_collateral_vault = await get_token_account(
        provider, clearing_house_state.collateral_vault
    )
    assert clearing_house_collateral_vault.amount == USDC_AMOUNT

    user_positions_account: UserPositions = await clearing_house.program.account[
        "UserPositions"
    ].fetch(user.positions)

    assert len(user_positions_account.positions) == 5
    assert user_positions_account.user == user_account_public_key
    assert user_positions_account.positions[0].base_asset_amount == 0
    assert user_positions_account.positions[0].quote_asset_amount == 0
    assert user_positions_account.positions[0].last_cumulative_funding_rate == 0

    deposit_history = await clearing_house.get_deposit_history_account()

    assert deposit_history.head == 1
    assert deposit_history.deposit_records[0].record_id == 1
    assert (
        deposit_history.deposit_records[0].user_authority == provider.wallet.public_key
    )
    assert deposit_history.deposit_records[0].user == user_account_public_key
    assert deposit_history.deposit_records[0].amount == 10000000
    assert deposit_history.deposit_records[0].collateral_before == 0
    assert deposit_history.deposit_records[0].cumulative_deposits_before == 0
