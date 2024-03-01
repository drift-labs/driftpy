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
async def drift_client(program: Program, usdc_mint: Keypair) -> Admin:
    admin = Admin(
        program.provider.connection,
        program.provider.wallet,
        account_subscription=AccountSubscriptionConfig("cached"),
    )
    await admin.initialize(usdc_mint.pubkey(), admin_controls_prices=True)
    await admin.subscribe()
    return admin


@async_fixture(scope="session")
async def first_oracle(workspace: WorkspaceType):
    oracle_price = 30
    oracle_program = workspace["pyth"]

    oracle = await mock_oracle(oracle_program, oracle_price, -7)
    return oracle


@async_fixture(scope="session")
async def other_oracle(workspace: WorkspaceType):
    oracle_price = 100
    oracle_program = workspace["pyth"]

    oracle = await mock_oracle(oracle_program, oracle_price, -7)
    return oracle


@mark.asyncio
async def test_quote_spot(
    drift_client: Admin,
    usdc_mint: Keypair,
):
    await drift_client.initialize_spot_market(usdc_mint.pubkey())


@mark.asyncio
async def test_sol_spot(drift_client: Admin, first_oracle: Pubkey):
    admin_drift_client = drift_client
    mint = await _create_mint(admin_drift_client.program.provider)

    await initialize_sol_spot_market(drift_client, first_oracle, mint.pubkey())

    spot_market = await get_spot_market_account(admin_drift_client.program, 1)
    assert spot_market.market_index == 1

    return spot_market


@mark.asyncio
async def test_sol_perp(drift_client: Admin, first_oracle: Pubkey):
    admin_drift_client = drift_client
    await drift_client.initialize_perp_market(
        0, first_oracle, AMM_INITIAL_BAA, AMM_INITIAL_QAA, 0, 30 * PEG_PRECISION
    )

    perp_market = await get_perp_market_account(admin_drift_client.program, 0)
    assert perp_market.market_index == 0

    return perp_market


@async_fixture(scope="session")
async def polling_drift_client(program: Program, first_oracle: Pubkey):
    oracle_infos = [OracleInfo(first_oracle, OracleSource.Pyth())]
    polling_drift_client = DriftClient(
        program.provider.connection,
        program.provider.wallet,
        account_subscription=AccountSubscriptionConfig(
            "polling",
            bulk_account_loader=BulkAccountLoader(program.provider.connection),
        ),
        spot_market_indexes=[0, 1],
        perp_market_indexes=[0],
        oracle_infos=oracle_infos,
    )
    await polling_drift_client.subscribe()

    return polling_drift_client


@async_fixture(scope="session")
async def ws_drift_client(program: Program, first_oracle: Pubkey):
    oracle_infos = [OracleInfo(first_oracle, OracleSource.Pyth())]
    ws_drift_client = DriftClient(
        program.provider.connection,
        program.provider.wallet,
        account_subscription=AccountSubscriptionConfig("websocket"),
        spot_market_indexes=[0, 1],
        perp_market_indexes=[0],
        oracle_infos=oracle_infos,
    )

    await ws_drift_client.subscribe()

    return ws_drift_client


@mark.asyncio
async def test_polling(
    drift_client: Admin,
    polling_drift_client: DriftClient,
    first_oracle: Pubkey,
    other_oracle: Pubkey,
):
    print()
    await drift_client.update_spot_market_oracle(1, first_oracle, OracleSource.Pyth())
    await drift_client.update_perp_market_oracle(0, first_oracle, OracleSource.Pyth())

    await drift_client.account_subscriber.fetch()
    await polling_drift_client.account_subscriber.fetch()

    await drift_client.update_perp_market_oracle(0, other_oracle, OracleSource.Pyth())

    await asyncio.sleep(20)

    perp_oracle_price_before = (polling_drift_client.get_oracle_price_data_for_perp_market(0)).price  # type: ignore
    print(f"perp_oracle_price_before: {perp_oracle_price_before}")
    assert perp_oracle_price_before == 30 * PRICE_PRECISION

    await asyncio.sleep(10)

    perp_oracle_price_after = (polling_drift_client.get_oracle_price_data_for_perp_market(0)).price  # type: ignore
    print(f"perp_oracle_price_after: {perp_oracle_price_after}")
    assert perp_oracle_price_after == 100 * PRICE_PRECISION

    await polling_drift_client.account_subscriber.fetch()

    await drift_client.update_spot_market_oracle(1, other_oracle, OracleSource.Pyth())

    await asyncio.sleep(20)

    spot_oracle_price_before = (polling_drift_client.get_oracle_price_data_for_spot_market(1)).price  # type: ignore
    print(f"spot_oracle_price_before: {spot_oracle_price_before}")
    assert spot_oracle_price_before == 30 * PRICE_PRECISION

    await asyncio.sleep(10)

    spot_oracle_price_after = (polling_drift_client.get_oracle_price_data_for_spot_market(1)).price  # type: ignore
    print(f"spot_oracle_price_after: {spot_oracle_price_after}")
    assert spot_oracle_price_after == 100 * PRICE_PRECISION


@mark.asyncio
async def test_ws(
    drift_client: Admin,
    ws_drift_client: DriftClient,
    first_oracle: Pubkey,
    other_oracle: Pubkey,
):
    print()
    assert ws_drift_client.account_subscriber.is_subscribed()
    print(first_oracle)
    print(other_oracle)

    await drift_client.update_spot_market_oracle(1, first_oracle, OracleSource.Pyth())
    await drift_client.update_perp_market_oracle(0, first_oracle, OracleSource.Pyth())

    await drift_client.update_perp_market_oracle(0, other_oracle, OracleSource.Pyth())
    await asyncio.sleep(45)

    print("what the actual fuck")
    perp_oracle_price_before = (
        ws_drift_client.get_oracle_price_data_for_perp_market(0)
    ).price
    print(f"perp_oracle_price_before: {perp_oracle_price_before}")
    assert perp_oracle_price_before == 30 * PRICE_PRECISION

    await asyncio.sleep(20)

    perp_oracle_price_after = (
        ws_drift_client.get_oracle_price_data_for_perp_market(0)
    ).price
    print(f"perp_oracle_price_after: {perp_oracle_price_after}")
    assert perp_oracle_price_after == 100 * PRICE_PRECISION

    await drift_client.update_spot_market_oracle(1, other_oracle, OracleSource.Pyth())
    await asyncio.sleep(45)

    spot_oracle_price_before = (
        ws_drift_client.get_oracle_price_data_for_spot_market(1)
    ).price
    print(f"spot_oracle_price_before: {spot_oracle_price_before}")
    assert spot_oracle_price_before == 30 * PRICE_PRECISION

    await asyncio.sleep(20)

    spot_oracle_price_after = (
        ws_drift_client.get_oracle_price_data_for_spot_market(1)
    ).price
    print(f"spot_oracle_price_after: {spot_oracle_price_after}")
    assert spot_oracle_price_after == 100 * PRICE_PRECISION
