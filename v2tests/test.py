import pytest
import asyncio
from pytest import fixture, mark
from pytest_asyncio import fixture as async_fixture
from anchorpy import Provider, WorkspaceType, workspace_fixture, Program
from solana.keypair import Keypair
from solana.transaction import Transaction
from solana.system_program import create_account, CreateAccountParams
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token._layouts import MINT_LAYOUT
from spl.token.async_client import AsyncToken
from spl.token.instructions import initialize_mint, InitializeMintParams

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
from driftpy.constants.numeric_constants import *
from math import sqrt
from typing import cast
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
from driftpy.constants.numeric_constants import PRICE_PRECISION, AMM_RESERVE_PRECISION
from driftpy.clearing_house import ClearingHouse
from driftpy.setup.helpers import _create_usdc_mint, _create_and_mint_user_usdc, mock_oracle, set_price_feed, _airdrop_user

from driftpy.addresses import * 
from driftpy.types import * 
from driftpy.accounts import *

MANTISSA_SQRT_SCALE = int(sqrt(PRICE_PRECISION))
AMM_INITIAL_QUOTE_ASSET_AMOUNT = int((5 * AMM_RESERVE_PRECISION) * MANTISSA_SQRT_SCALE)
AMM_INITIAL_BASE_ASSET_AMOUNT = int((5 * AMM_RESERVE_PRECISION) * MANTISSA_SQRT_SCALE)
PERIODICITY = 60 * 60  # 1 HOUR
USDC_AMOUNT = int(10 * QUOTE_PRECISION)
MARKET_INDEX = 0

workspace = workspace_fixture(
    "protocol-v2", build_cmd="anchor build --skip-lint", scope="session"
)

@async_fixture(scope="session")
async def usdc_mint(provider: Provider):
    return await _create_usdc_mint(provider)

@async_fixture(scope="session")
async def user_usdc_account(
    usdc_mint: Keypair,
    provider: Provider,
):
    return await _create_and_mint_user_usdc(
        usdc_mint, 
        provider, 
        USDC_AMOUNT * 2, 
        provider.wallet.public_key
    )

@fixture(scope="session")
def program(workspace: WorkspaceType) -> Program:
    """Create a Program instance."""
    return workspace["clearing_house"]

@fixture(scope="session")
def provider(program: Program) -> Provider:
    return program.provider

@async_fixture(scope="session")
async def clearing_house(program: Program, usdc_mint: Keypair) -> Admin:
    admin = Admin(program)
    await admin.initialize(usdc_mint.public_key, admin_controls_prices=True)
    return admin 

@async_fixture(scope="session")
async def initialized_spot_market(
    clearing_house: Admin, 
    usdc_mint: Keypair,
): 
    await clearing_house.initialize_spot_market(
        usdc_mint.public_key 
    )

@async_fixture(scope="session")
async def initialized_market(
    clearing_house: Admin, workspace: WorkspaceType
) -> PublicKey:
    pyth_program = workspace["pyth"]
    sol_usd = await mock_oracle(pyth_program=pyth_program, price=1)

    await clearing_house.initialize_perp_market(
        sol_usd,
        AMM_INITIAL_BASE_ASSET_AMOUNT,
        AMM_INITIAL_QUOTE_ASSET_AMOUNT,
        PERIODICITY,
    )

    return sol_usd

@mark.asyncio
async def test_spot(
    clearing_house: Admin,
    initialized_spot_market: PublicKey,
):
    program = clearing_house.program
    spot_market = await get_spot_market_account(program, 0)
    assert spot_market.market_index == 0 

@mark.asyncio
async def test_market(
    clearing_house: Admin,
    initialized_market: PublicKey,
):
    program = clearing_house.program
    market_oracle_public_key = initialized_market
    market: PerpMarket = await get_perp_market_account(program, 0)

    assert market.amm.oracle == market_oracle_public_key

@mark.asyncio
async def test_init_user(
    clearing_house: Admin,
):
    await clearing_house.intialize_user()
    user: User = await get_user_account(
        clearing_house.program, 
        clearing_house.authority, 
        user_id=0
    )
    assert user.authority == clearing_house.authority


@mark.asyncio
async def test_usdc_deposit(
    clearing_house: Admin,
    user_usdc_account: Keypair,
):
    clearing_house.usdc_ata = user_usdc_account.public_key
    await clearing_house.deposit(
        USDC_AMOUNT, 
        0, 
        user_usdc_account.public_key, 
        user_initialized=True
    )
    user_account = await get_user_account(
        clearing_house.program, 
        clearing_house.authority
    )
    assert user_account.spot_positions[0].scaled_balance == USDC_AMOUNT / QUOTE_PRECISION * SPOT_BALANCE_PRECISION


@mark.asyncio
async def test_add_remove_liquidity(
    clearing_house: Admin,
):
    market = await get_perp_market_account(clearing_house.program, 0)
    n_shares = market.amm.order_step_size

    await clearing_house.update_lp_cooldown_time(0)
    state = await get_state_account(clearing_house.program)
    assert state.lp_cooldown_time == 0

    await clearing_house.add_liquidity(
        n_shares, 
        0
    )
    user_account = await get_user_account(
        clearing_house.program, 
        clearing_house.authority
    )
    assert user_account.perp_positions[0].lp_shares == n_shares

    await clearing_house.settle_lp(
        clearing_house.authority, 
        0
    )

    await clearing_house.remove_liquidity(
        n_shares, 0
    )
    user_account = await get_user_account(
        clearing_house.program, 
        clearing_house.authority
    )
    assert user_account.perp_positions[0].lp_shares == 0

@mark.asyncio
async def test_open_close_position(
    clearing_house: Admin,
):
    await clearing_house.update_perp_auction_duration(
        0
    )

    baa = 10 * AMM_RESERVE_PRECISION
    sig = await clearing_house.open_position(
        PositionDirection.LONG(), 
        baa, 
        0,
    )

    from solana.rpc.commitment import Confirmed, Processed
    clearing_house.program.provider.connection._commitment = Confirmed
    tx = await clearing_house.program.provider.connection.get_transaction(sig)
    clearing_house.program.provider.connection._commitment = Processed
    # print(tx)
    
    user_account = await get_user_account(
        clearing_house.program, 
        clearing_house.authority
    )

    assert user_account.perp_positions[0].base_asset_amount == baa
    assert user_account.perp_positions[0].quote_asset_amount < 0

    await clearing_house.close_position(
        0
    )

    user_account = await get_user_account(
        clearing_house.program, 
        clearing_house.authority
    )
    assert user_account.perp_positions[0].base_asset_amount == 0
    assert user_account.perp_positions[0].quote_asset_amount < 0

@mark.asyncio
async def test_stake_if(
    clearing_house: Admin,
    user_usdc_account: Keypair,
):
    # important
    clearing_house.usdc_ata = user_usdc_account.public_key

    await clearing_house.initialize_insurance_fund_stake(
        0
    )
    if_acc = await get_if_stake_account(
        clearing_house.program, 
        clearing_house.authority, 
        0
    )
    assert if_acc.market_index == 0 

    await clearing_house.add_insurance_fund_stake(
        0, 1 * QUOTE_PRECISION
    )

    ch = clearing_house
    user_stats = await get_user_stats_account(ch.program, ch.authority)
    assert user_stats.if_staked_quote_asset_amount == 1 * QUOTE_PRECISION

    await clearing_house.request_remove_insurance_fund_stake(
        0, 1 * QUOTE_PRECISION
    )

    await clearing_house.remove_insurance_fund_stake(
        0
    )

    user_stats = await get_user_stats_account(ch.program, ch.authority)
    assert user_stats.if_staked_quote_asset_amount == 0


# note this goes at end bc the main clearing house loses all collateral ...
@mark.asyncio
async def test_liq_perp(
    clearing_house: Admin,
    usdc_mint: Keypair,
    workspace: WorkspaceType
):
    market = await get_perp_market_account(clearing_house.program, 0)
    user_account = await get_user_account(
        clearing_house.program, 
        clearing_house.authority
    )

    liq, _ = await _airdrop_user(clearing_house.program.provider)
    liq_ch = ClearingHouse(clearing_house.program, liq)
    usdc_acc = await _create_and_mint_user_usdc(
        usdc_mint, 
        clearing_house.program.provider, 
        USDC_AMOUNT, 
        liq.public_key
    )
    await liq_ch.intialize_user()
    await liq_ch.deposit(
        USDC_AMOUNT, 
        0, 
        usdc_acc.public_key, 
    )

    from driftpy.constants.numeric_constants import AMM_RESERVE_PRECISION
    from driftpy.math.amm import calculate_price
    price = calculate_price(market.amm.base_asset_reserve, market.amm.quote_asset_reserve, market.amm.peg_multiplier)
    baa = user_account.spot_positions[0].scaled_balance / price / SPOT_BALANCE_PRECISION * AMM_RESERVE_PRECISION * 3
    await clearing_house.open_position(
        PositionDirection.SHORT(), 
        int(baa),
        0, 
    )

    # liq em
    pyth_program = workspace["pyth"]
    await set_price_feed(pyth_program, market.amm.oracle, 1.5)

    sig = await liq_ch.liquidate_perp(
        clearing_house.authority, 
        0, 
        int(baa) // 10
    )

    # liq takes on position
    position = await liq_ch.get_user_position(0)
    assert position.base_asset_amount != 0 