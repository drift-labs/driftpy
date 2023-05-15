from pytest import fixture, mark
from pytest_asyncio import fixture as async_fixture
from solana.keypair import Keypair
from solana.publickey import PublicKey
from anchorpy import Program, Provider, WorkspaceType, workspace_fixture
from driftpy.admin import Admin
from driftpy.constants.numeric_constants import (
    PRICE_PRECISION,
    AMM_RESERVE_PRECISION,
    QUOTE_PRECISION,
    SPOT_BALANCE_PRECISION,
    SPOT_WEIGHT_PRECISION,
)
from math import sqrt

from driftpy.clearing_house import ClearingHouse
from driftpy.setup.helpers import (
    _create_mint,
    _create_and_mint_user_usdc,
    mock_oracle,
    set_price_feed,
    _airdrop_user,
)

from driftpy.addresses import *
from driftpy.types import (
    User,
    PositionDirection,
    OracleSource,
    PerpMarket,
    # SwapDirection,
)
from driftpy.accounts import (
    get_user_account,
    get_user_stats_account,
    get_perp_market_account,
    get_spot_market_account,
    get_state_account,
    get_if_stake_account,
)

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
    return await _create_mint(provider)


@async_fixture(scope="session")
async def user_usdc_account(
    usdc_mint: Keypair,
    provider: Provider,
):
    return await _create_and_mint_user_usdc(
        usdc_mint, provider, USDC_AMOUNT * 2, provider.wallet.public_key
    )


@fixture(scope="session")
def program(workspace: WorkspaceType) -> Program:
    """Create a Program instance."""
    return workspace["drift"]


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
    await clearing_house.initialize_spot_market(usdc_mint.public_key)


@mark.asyncio
async def test_initialized_spot_market_2(
    clearing_house: Admin, initialized_spot_market, workspace: WorkspaceType
):
    admin_clearing_house = clearing_house
    oracle_price = 1
    oracle_program = workspace["pyth"]

    oracle = await mock_oracle(oracle_program, oracle_price, -7)
    mint = await _create_mint(admin_clearing_house.program.provider)

    optimal_util = SPOT_WEIGHT_PRECISION // 2
    optimal_weight = int(SPOT_WEIGHT_PRECISION * 20)
    max_rate = int(SPOT_WEIGHT_PRECISION * 50)

    init_weight = int(SPOT_WEIGHT_PRECISION * 8 / 10)
    main_weight = int(SPOT_WEIGHT_PRECISION * 9 / 10)

    init_liab_weight = int(SPOT_WEIGHT_PRECISION * 12 / 10)
    main_liab_weight = int(SPOT_WEIGHT_PRECISION * 11 / 10)

    await admin_clearing_house.initialize_spot_market(
        mint.public_key,
        oracle=oracle,
        optimal_utilization=optimal_util,
        optimal_rate=optimal_weight,
        max_rate=max_rate,
        oracle_source=OracleSource.PYTH(),
        initial_asset_weight=init_weight,
        maintenance_asset_weight=main_weight,
        initial_liability_weight=init_liab_weight,
        maintenance_liability_weight=main_liab_weight,
    )

    spot_market = await get_spot_market_account(admin_clearing_house.program, 1)
    assert spot_market.market_index == 1
    print(spot_market.market_index)


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
        clearing_house.program, clearing_house.authority, subaccount_id=0
    )
    assert user.authority == clearing_house.authority


@mark.asyncio
async def test_usdc_deposit(
    clearing_house: Admin,
    user_usdc_account: Keypair,
):
    clearing_house.spot_market_atas[0] = user_usdc_account.public_key
    await clearing_house.deposit(
        USDC_AMOUNT, 0, user_usdc_account.public_key, user_initialized=True
    )
    user_account = await get_user_account(
        clearing_house.program, clearing_house.authority
    )
    assert (
        user_account.spot_positions[0].scaled_balance
        == USDC_AMOUNT / QUOTE_PRECISION * SPOT_BALANCE_PRECISION
    )


@mark.asyncio
async def test_update_curve(
    workspace,
    clearing_house: Admin,
):
    market = await get_perp_market_account(clearing_house.program, 0)
    new_sqrt_k = int(market.amm.sqrt_k * 1.05)
    await clearing_house.update_k(new_sqrt_k, 0)
    market = await get_perp_market_account(clearing_house.program, 0)
    assert market.amm.sqrt_k == new_sqrt_k

    from driftpy.setup.helpers import set_price_feed_detailed

    pyth_program = workspace["pyth"]
    slot = (await clearing_house.program.provider.connection.get_slot())["result"]
    await set_price_feed_detailed(pyth_program, market.amm.oracle, 1.07, 0, slot)

    new_peg = int(market.amm.peg_multiplier * 1.05)
    await clearing_house.repeg_curve(new_peg, 0)
    market = await get_perp_market_account(clearing_house.program, 0)
    assert market.amm.peg_multiplier == new_peg


@mark.asyncio
async def test_add_remove_liquidity(
    clearing_house: Admin,
):
    market = await get_perp_market_account(clearing_house.program, 0)
    n_shares = market.amm.order_step_size

    await clearing_house.update_lp_cooldown_time(0)
    state = await get_state_account(clearing_house.program)
    assert state.lp_cooldown_time == 0

    await clearing_house.add_liquidity(n_shares, 0)
    user_account = await get_user_account(
        clearing_house.program, clearing_house.authority
    )
    assert user_account.perp_positions[0].lp_shares == n_shares

    await clearing_house.settle_lp(clearing_house.authority, 0)

    await clearing_house.remove_liquidity(n_shares, 0)
    user_account = await get_user_account(
        clearing_house.program, clearing_house.authority
    )
    assert user_account.perp_positions[0].lp_shares == 0


@mark.asyncio
async def test_update_amm(clearing_house: Admin, workspace):
    market = await get_perp_market_account(clearing_house.program, 0)
    # provider: Provider = clearing_house.program.provider

    # pyth_program = workspace["pyth"]
    # await set_price_feed(pyth_program, market.amm.oracle, 1.5)
    # signer2 = pyth_program.provider.wallet.payer
    # ix1 = await get_set_price_feed_detailed_ix(
    #     pyth_program, market.amm.oracle, 1, 0, 1
    # )

    ix2 = await clearing_house.get_update_amm_ix([0])
    ixs = [ix2]

    # ixs = [ix1, ix2]

    await clearing_house.send_ixs(ixs)
    market_after = await get_perp_market_account(clearing_house.program, 0)
    assert market.amm.last_update_slot != market_after.amm.last_update_slot


@mark.asyncio
async def test_open_close_position(
    clearing_house: Admin,
):
    await clearing_house.update_perp_auction_duration(0)

    baa = 10 * AMM_RESERVE_PRECISION
    sig = await clearing_house.open_position(
        PositionDirection.LONG(),
        baa,
        0,
    )

    from solana.rpc.commitment import Confirmed, Processed

    clearing_house.program.provider.connection._commitment = Confirmed
    await clearing_house.program.provider.connection.get_transaction(sig)
    clearing_house.program.provider.connection._commitment = Processed
    # print(tx)

    user_account = await get_user_account(
        clearing_house.program, clearing_house.authority
    )

    assert user_account.perp_positions[0].base_asset_amount == baa
    assert user_account.perp_positions[0].quote_asset_amount < 0

    await clearing_house.close_position(0)

    user_account = await get_user_account(
        clearing_house.program, clearing_house.authority
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

    await clearing_house.update_update_insurance_fund_unstaking_period(0, 0)

    await clearing_house.initialize_insurance_fund_stake(0)
    if_acc = await get_if_stake_account(
        clearing_house.program, clearing_house.authority, 0
    )
    assert if_acc.market_index == 0

    await clearing_house.add_insurance_fund_stake(0, 1 * QUOTE_PRECISION)

    ch = clearing_house
    user_stats = await get_user_stats_account(ch.program, ch.authority)
    assert user_stats.if_staked_quote_asset_amount == 1 * QUOTE_PRECISION

    await clearing_house.request_remove_insurance_fund_stake(0, 1 * QUOTE_PRECISION)

    await clearing_house.remove_insurance_fund_stake(0)

    user_stats = await get_user_stats_account(ch.program, ch.authority)
    assert user_stats.if_staked_quote_asset_amount == 0


# note this goes at end bc the main clearing house loses all collateral ...
@mark.asyncio
async def test_liq_perp(
    clearing_house: Admin, usdc_mint: Keypair, workspace: WorkspaceType
):
    market = await get_perp_market_account(clearing_house.program, 0)
    user_account = await get_user_account(
        clearing_house.program, clearing_house.authority
    )

    liq, _ = await _airdrop_user(clearing_house.program.provider)
    liq_ch = ClearingHouse(clearing_house.program, liq)
    usdc_acc = await _create_and_mint_user_usdc(
        usdc_mint, clearing_house.program.provider, USDC_AMOUNT, liq.public_key
    )
    await liq_ch.intialize_user()
    await liq_ch.deposit(
        USDC_AMOUNT,
        0,
        usdc_acc.public_key,
    )

    from driftpy.constants.numeric_constants import AMM_RESERVE_PRECISION
    from driftpy.math.amm import calculate_price

    price = calculate_price(
        market.amm.base_asset_reserve,
        market.amm.quote_asset_reserve,
        market.amm.peg_multiplier,
    )
    baa = (
        user_account.spot_positions[0].scaled_balance
        / price
        / SPOT_BALANCE_PRECISION
        * AMM_RESERVE_PRECISION
        * 3
    )
    await clearing_house.open_position(
        PositionDirection.SHORT(),
        int(baa),
        0,
    )

    # liq em
    pyth_program = workspace["pyth"]
    await set_price_feed(pyth_program, market.amm.oracle, 1.5)

    await liq_ch.liquidate_perp(clearing_house.authority, 0, int(baa) // 10)

    # liq takes on position
    position = await liq_ch.get_user_position(0)
    assert position.base_asset_amount != 0
