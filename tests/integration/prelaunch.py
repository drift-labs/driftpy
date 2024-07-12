import asyncio
from math import sqrt

from pytest import fixture, mark
from pytest_asyncio import fixture as async_fixture
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from anchorpy import Program, Provider, WorkspaceType, workspace_fixture
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.accounts.bulk_account_loader import BulkAccountLoader
from driftpy.accounts.get_accounts import (
    get_perp_market_account,
    get_spot_market_account,
)
from driftpy.addresses import get_prelaunch_oracle_public_key

from driftpy.constants.numeric_constants import *
from driftpy.admin import Admin
from driftpy.drift_client import DriftClient
from driftpy.setup.helpers import (
    _create_mint,
    _create_and_mint_user_usdc,
    mock_oracle,
    set_price_feed,
)
from driftpy.types import *
from driftpy.setup.helpers import initialize_sol_spot_market

workspace = workspace_fixture("protocol-v2", build_cmd="anchor build", scope="session")


USDC_AMOUNT = 10 * QUOTE_PRECISION
LARGE_USDC_AMOUNT = 10_000 * QUOTE_PRECISION
MANTISSA_SQRT_SCALE = int(sqrt(PRICE_PRECISION))
AMM_INITIAL_BAA = (5 * 10**13) * MANTISSA_SQRT_SCALE
AMM_INITIAL_QAA = (5 * 10**13) * MANTISSA_SQRT_SCALE


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
async def admin(program: Program, usdc_mint: Keypair) -> Admin:
    prelaunch_oracle = get_prelaunch_oracle_public_key(program.program_id, 0)
    oracle_infos = [OracleInfo(prelaunch_oracle, OracleSource.Prelaunch())]
    admin = Admin(
        program.provider.connection,
        program.provider.wallet,
        perp_market_indexes=[0],
        spot_market_indexes=[0, 1],
        oracle_infos=oracle_infos,
    )
    await admin.initialize(usdc_mint.pubkey(), admin_controls_prices=True)
    await admin.subscribe()
    return admin


@async_fixture
async def prelaunch_oracle(program: Program, admin: Admin) -> Pubkey:
    start_price = PRICE_PRECISION * 32
    max_price = start_price * 4
    await admin.initialize_prelaunch_oracle(0, start_price, max_price)
    return get_prelaunch_oracle_public_key(program.program_id, 0)


@mark.asyncio
async def test_quote_spot(
    admin: Admin,
    usdc_mint: Keypair,
):
    await admin.initialize_spot_market(usdc_mint.pubkey())


@mark.asyncio
async def test_sol_perp(admin: Admin, prelaunch_oracle: Pubkey):
    print("prelaunch_oracle", prelaunch_oracle)
    await admin.initialize_perp_market(
        0,
        prelaunch_oracle,
        AMM_INITIAL_BAA,
        AMM_INITIAL_QAA,
        3_600,
        32 * PEG_PRECISION,
        OracleSource.Prelaunch(),
    )

    perp_market = await get_perp_market_account(admin.program, 0)
    assert perp_market.market_index == 0

    await admin.update_perp_auction_duration(0)
    await admin.update_perp_market_base_spread(0, BID_ASK_SPREAD_PRECISION // 50)

    return perp_market


@mark.asyncio
async def test_trade(admin: Admin, usdc_mint: Keypair):
    prelaunch_oracle = get_prelaunch_oracle_public_key(admin.program.program_id, 0)
    oracle_infos = [OracleInfo(prelaunch_oracle, OracleSource.Prelaunch())]
    drift_client = DriftClient(
        admin.program.provider.connection,
        admin.program.provider.wallet,
        perp_market_indexes=[0],
        spot_market_indexes=[0, 1],
        oracle_infos=oracle_infos,
    )
    await drift_client.subscribe()

    usdc_acc = await _create_and_mint_user_usdc(
        usdc_mint,
        admin.program.provider,
        USDC_AMOUNT,
        drift_client.program.provider.wallet.public_key,
    )
    await drift_client.initialize_user()
    await drift_client.add_user(0)

    while True:
        try:
            drift_client.get_user_account()
            await asyncio.sleep(1)
            break
        except AttributeError:
            print("retrying...")
            await asyncio.sleep(1)

    await drift_client.deposit(USDC_AMOUNT, 0, usdc_acc.pubkey())

    market_index = 0
    base_asset_amount = BASE_PRECISION
    bid_order_params = OrderParams(
        market_index=market_index,
        direction=PositionDirection.Long(),
        base_asset_amount=base_asset_amount,
        price=int(34 * PRICE_PRECISION),
        auction_start_price=int(33 * PRICE_PRECISION),
        auction_end_price=int(34 * PRICE_PRECISION),
        auction_duration=10,
        user_order_id=1,
        post_only=PostOnlyParams.NONE(),
        order_type=OrderType.Limit(),
    )
    await drift_client.place_perp_order(bid_order_params)
    admin_user = drift_client.get_user()
    while admin_user.get_order_by_user_order_id(1) is None:
        await asyncio.sleep(1)
    bid_order = admin_user.get_order_by_user_order_id(1)

    await admin.fill_perp_order(
        drift_client.get_user_account_public_key(),
        admin_user.get_user_account(),
        bid_order,
        None,
        None,
    )

    await drift_client.update_prelaunch_oracle(0)

    tries = 0
    while tries < 50:
        if drift_client.get_oracle_price_data_for_perp_market(0):
            oracle_price_data_after_buy = (
                drift_client.get_oracle_price_data_for_perp_market(0)
            )
            if oracle_price_data_after_buy.price > 32_000_000:
                break
        print("retrying")
        await asyncio.sleep(1)
        tries += 1

    if tries == 50:
        assert False
    print("oracle_price_data_after_buy", oracle_price_data_after_buy)

    ask_order_params = OrderParams(
        market_index=market_index,
        direction=PositionDirection.Short(),
        base_asset_amount=base_asset_amount,
        price=int(30 * PRICE_PRECISION),
        auction_start_price=int(31 * PRICE_PRECISION),
        auction_end_price=int(30 * PRICE_PRECISION),
        auction_duration=10,
        user_order_id=2,
        post_only=PostOnlyParams.NONE(),
        order_type=OrderType.Limit(),
    )

    await drift_client.place_perp_order(ask_order_params)

    admin_user = drift_client.get_user()
    while admin_user.get_order_by_user_order_id(2) is None:
        await asyncio.sleep(1)
    ask_order = admin_user.get_order_by_user_order_id(2)

    await admin.fill_perp_order(
        drift_client.get_user_account_public_key(),
        admin_user.get_user_account(),
        ask_order,
        None,
        None,
    )

    await drift_client.update_prelaunch_oracle(0)

    while tries < 50:
        if drift_client.get_oracle_price_data_for_perp_market(0):
            oracle_price_data_after_sell = (
                drift_client.get_oracle_price_data_for_perp_market(0)
            )
            if oracle_price_data_after_sell.price < oracle_price_data_after_buy.price:
                break
        print("retrying")
        await asyncio.sleep(1)
        tries += 1

    print("oracle_price_data_after_sell", oracle_price_data_after_sell)

    if tries == 50:
        assert False


@mark.asyncio
async def test_update_params(admin: Admin):
    new_price = PRICE_PRECISION * 40
    max_price = new_price * 4
    await admin.update_prelaunch_oracle_params(0, new_price, max_price)

    prelaunch_oracle = get_prelaunch_oracle_public_key(admin.program.program_id, 0)
    oracle_infos = [OracleInfo(prelaunch_oracle, OracleSource.Prelaunch())]
    drift_client = DriftClient(
        admin.program.provider.connection,
        admin.program.provider.wallet,
        perp_market_indexes=[0],
        spot_market_indexes=[0, 1],
        oracle_infos=oracle_infos,
    )
    await drift_client.subscribe()

    tries = 0
    while tries < 50:
        oracle_price_data = drift_client.get_oracle_price_data_for_perp_market(0)
        if oracle_price_data:
            if oracle_price_data.price == new_price:
                break

    if tries == 50:
        assert False
