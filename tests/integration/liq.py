import asyncio
from math import sqrt

from pytest import fixture, mark
import pytest
from pytest_asyncio import fixture as async_fixture
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from anchorpy import Program, Provider, WorkspaceType, workspace_fixture
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.accounts.get_accounts import (
    get_perp_market_account,
    get_spot_market_account,
)
from driftpy.admin import Admin
from driftpy.constants.numeric_constants import *

from driftpy.math.margin import MarginCategory
from driftpy.setup.helpers import (
    _create_mint,
    _create_and_mint_user_usdc,
    mock_oracle,
    set_price_feed,
)
from driftpy.types import PerpMarketAccount, PositionDirection

MANTISSA_SQRT_SCALE = int(sqrt(PRICE_PRECISION))
AMM_INITIAL_QUOTE_ASSET_AMOUNT = int((5 * 10**13) * MANTISSA_SQRT_SCALE)
AMM_INITIAL_BASE_ASSET_AMOUNT = int((5 * 10**13) * MANTISSA_SQRT_SCALE)
PERIODICITY = 0
USDC_AMOUNT = int(10 * QUOTE_PRECISION)
MARKET_INDEX = 0
N_LP_SHARES = 0
LIQUIDATION_DEVIATION_TOLERANCE = 0.0001

workspace = workspace_fixture("protocol-v2", build_cmd="anchor build", scope="session")


@pytest.fixture(scope="session")
def event_loop():
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


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
async def drift_client(program: Program, usdc_mint: Keypair) -> Admin:
    admin = Admin(
        program.provider.connection,
        program.provider.wallet,
        account_subscription=AccountSubscriptionConfig("cached"),
        spot_market_indexes=[0],
        perp_market_indexes=[0],
    )
    await admin.initialize(usdc_mint.pubkey(), admin_controls_prices=True)
    await admin.subscribe()
    await admin.update_initial_percent_to_liquidate(LIQUIDATION_PCT_PRECISION)
    await admin.update_perp_auction_duration(0)
    return admin


@async_fixture(scope="session")
async def initialized_spot_market(
    drift_client: Admin,
    usdc_mint: Keypair,
):
    await drift_client.initialize_spot_market(usdc_mint.pubkey())
    await drift_client.account_subscriber.update_cache()


@async_fixture(scope="session")
async def initialized_market(drift_client: Admin, workspace: WorkspaceType) -> Pubkey:
    pyth_program = workspace["pyth"]
    sol_usd = await mock_oracle(pyth_program=pyth_program, price=1)
    perp_market_index = 0
    await drift_client.initialize_perp_market(
        perp_market_index,
        sol_usd,
        AMM_INITIAL_BASE_ASSET_AMOUNT,
        AMM_INITIAL_QUOTE_ASSET_AMOUNT,
        PERIODICITY,
    )

    await drift_client.account_subscriber.update_cache()

    return sol_usd


@mark.asyncio
async def test_spot(
    drift_client: Admin,
):
    program = drift_client.program
    spot_market = await get_spot_market_account(program, 0)
    assert spot_market.market_index == 0


@mark.asyncio
async def test_market(
    drift_client: Admin,
    initialized_market: Pubkey,
):
    program = drift_client.program
    market_oracle_public_key = initialized_market
    market: PerpMarketAccount = await get_perp_market_account(program, 0)

    assert market.amm.oracle == market_oracle_public_key


@mark.asyncio
async def test_perp_liq_price(
    drift_client: Admin, usdc_mint: Keypair, workspace: WorkspaceType
):
    pyth_program = workspace["pyth"]
    usdc_acc = await _create_and_mint_user_usdc(
        usdc_mint,
        drift_client.program.provider,
        USDC_AMOUNT,
        drift_client.program.provider.wallet.public_key,
    )
    await drift_client.initialize_user()
    await drift_client.add_user(0)
    await drift_client.get_user(0).account_subscriber.update_cache()
    await drift_client.deposit(USDC_AMOUNT, 0, usdc_acc.pubkey())
    await drift_client.open_position(
        PositionDirection.Long(),
        (175 * BASE_PRECISION) // 10,
        0,
        0,  # 17.5 SOL
    )

    lp_shares = drift_client.get_user_account().perp_positions[0].lp_shares
    assert lp_shares == N_LP_SHARES

    drift_user = drift_client.get_user(0)

    await drift_user.subscribe()

    maintenance_total_collateral = drift_user.get_total_collateral(
        MarginCategory.MAINTENANCE
    )
    maintenance_margin_requirement = drift_user.get_margin_requirement(
        MarginCategory.MAINTENANCE
    )
    perp_position = drift_user.get_perp_position(0)

    delta_value_to_liquidate = (
        maintenance_total_collateral - maintenance_margin_requirement
    )

    print("\nuser stats (initial):")
    print(f"total collateral: {maintenance_total_collateral}")
    print(f"margin requirement: {maintenance_margin_requirement}")
    print(f"delta value to liquidate: {delta_value_to_liquidate}")
    print(f"perp position base asset amount: {perp_position.base_asset_amount}")

    expected_liq_price = 0.45219
    liquidation_price = drift_user.get_perp_liq_price(0, 0)
    deviation = 1 - (liquidation_price / (expected_liq_price * PRICE_PRECISION))
    formatted_deviation = "{:.20f}".format(deviation)

    print(f"liquidation price: {liquidation_price}")
    print(f"expected liquidation price: {expected_liq_price * PRICE_PRECISION}")
    print(f"deviation: {formatted_deviation}")

    assert deviation < LIQUIDATION_DEVIATION_TOLERANCE

    print()

    oracle = drift_client.get_perp_market_account(0).amm.oracle
    print(f"setting oracle price: {0.9 * PRICE_PRECISION}")
    await set_price_feed(pyth_program, oracle, 0.9)

    await asyncio.sleep(2)

    await drift_client.account_subscriber.update_cache()
    await drift_user.account_subscriber.update_cache()

    oracle_price = drift_client.get_oracle_price_data_for_perp_market(0).price
    expected_oracle_price = 0.9 * PRICE_PRECISION
    print(f"updated oracle price: {oracle_price}")
    assert abs(oracle_price - expected_oracle_price) == 0.0

    liq_price_after_oracle_change = drift_user.get_perp_liq_price(0, 0)
    deviation = 1 - (
        liq_price_after_oracle_change / (expected_liq_price * PRICE_PRECISION)
    )
    formatted_deviation = "{:.20f}".format(deviation)

    print(f"liquidation price: {liq_price_after_oracle_change}")
    print(f"expected liquidation price: {expected_liq_price * PRICE_PRECISION}")
    print(f"deviation: {formatted_deviation}")

    assert deviation < LIQUIDATION_DEVIATION_TOLERANCE

    print()

    await drift_client.settle_pnl(
        drift_user.user_public_key, drift_user.get_user_account(), 0
    )

    await asyncio.sleep(2)

    await drift_client.account_subscriber.update_cache()
    await drift_user.account_subscriber.update_cache()

    oracle_price = drift_client.get_oracle_price_data_for_perp_market(0).price
    print(f"oracle price: {oracle_price}")
    assert abs(oracle_price - expected_oracle_price) == 0.0

    maintenance_total_collateral = drift_user.get_total_collateral(
        MarginCategory.MAINTENANCE
    )
    maintenance_margin_requirement = drift_user.get_margin_requirement(
        MarginCategory.MAINTENANCE
    )
    perp_position = drift_user.get_perp_position(0)

    delta_value_to_liquidate = (
        maintenance_total_collateral - maintenance_margin_requirement
    )

    print("user stats (after settle):")
    print(f"total collateral: {maintenance_total_collateral}")
    print(f"margin requirement: {maintenance_margin_requirement}")
    print(f"delta value to liquidate: {delta_value_to_liquidate}")
    print(f"perp position base asset amount: {perp_position.base_asset_amount}")

    liq_price_after_settle_pnl = drift_user.get_perp_liq_price(0, 0)
    deviation = 1 - (
        liq_price_after_settle_pnl / (expected_liq_price * PRICE_PRECISION)
    )
    formatted_deviation = "{:.20f}".format(deviation)

    print(f"liquidation price: {liq_price_after_settle_pnl}")
    print(f"expected liquidation price: {expected_liq_price * PRICE_PRECISION}")
    print(f"deviation: {formatted_deviation}")

    assert deviation < LIQUIDATION_DEVIATION_TOLERANCE

    print()

    print(f"setting oracle price: {1.1 * PRICE_PRECISION}")
    await set_price_feed(pyth_program, oracle, 1.1)

    await asyncio.sleep(2)

    await drift_client.account_subscriber.update_cache()
    await drift_user.account_subscriber.update_cache()

    oracle_price = drift_client.get_oracle_price_data_for_perp_market(0).price
    expected_oracle_price = 1.1 * PRICE_PRECISION
    print(f"updated oracle price: {oracle_price}")
    assert abs(oracle_price - expected_oracle_price) == 0.0

    await drift_client.settle_pnl(
        drift_user.user_public_key, drift_user.get_user_account(), 0
    )

    liq_price_after_rally_settle_pnl = drift_user.get_perp_liq_price(0, 0)
    deviation = 1 - (
        liq_price_after_rally_settle_pnl / (expected_liq_price * PRICE_PRECISION)
    )
    formatted_deviation = "{:.20f}".format(deviation)

    print(f"liquidation price: {liq_price_after_rally_settle_pnl}")
    print(f"expected liquidation price: {expected_liq_price * PRICE_PRECISION}")
    print(f"deviation: {formatted_deviation}")

    assert deviation < LIQUIDATION_DEVIATION_TOLERANCE
