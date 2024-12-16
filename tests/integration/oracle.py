import asyncio
from math import sqrt

from anchorpy.program.core import Program
from anchorpy.provider import Provider
from anchorpy.pytest_plugin import workspace_fixture
from anchorpy.workspace import WorkspaceType
from pytest import fixture, mark
from pytest_asyncio import fixture as async_fixture
from solana.rpc.commitment import Commitment
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.accounts.bulk_account_loader import BulkAccountLoader
from driftpy.accounts.get_accounts import (
    get_perp_market_account,
    get_spot_market_account,
)
from driftpy.accounts.ws.account_subscriber import WebsocketAccountSubscriber
from driftpy.admin import Admin
from driftpy.constants.numeric_constants import (
    PEG_PRECISION,
    PRICE_PRECISION,
    QUOTE_PRECISION,
)
from driftpy.drift_client import DriftClient
from driftpy.setup.helpers import (
    _create_and_mint_user_usdc,
    _create_mint,
    initialize_sol_spot_market,
    mock_oracle,
)
from driftpy.types import OracleInfo, OracleSource

workspace = workspace_fixture("protocol-v2", scope="session", build_cmd="")


USDC_AMOUNT = 10 * QUOTE_PRECISION
LARGE_USDC_AMOUNT = 10_000 * QUOTE_PRECISION
MANTISSA_SQRT_SCALE = int(sqrt(PRICE_PRECISION))
AMM_INITIAL_BAA = (5 * 10**13) * MANTISSA_SQRT_SCALE
AMM_INITIAL_QAA = (5 * 10**13) * MANTISSA_SQRT_SCALE


@fixture(scope="session")
def event_loop():
    """This must absolutely not be async fixture, it must be a normal fixture"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
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
async def test_dependency_injection(
    drift_client: Admin,
    usdc_mint: Keypair,
):
    ic(drift_client)
    ic(usdc_mint)


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


@mark.asyncio
async def test_polling(
    drift_client: Admin, first_oracle: Pubkey, other_oracle: Pubkey, program: Program
):
    await drift_client.update_spot_market_oracle(1, first_oracle, OracleSource.Pyth())  # type: ignore
    await drift_client.update_perp_market_oracle(0, first_oracle, OracleSource.Pyth())  # type: ignore

    oracle_infos = [OracleInfo(first_oracle, OracleSource.Pyth())]  # type: ignore
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

    assert polling_drift_client.account_subscriber is not None
    assert drift_client.account_subscriber is not None

    await drift_client.account_subscriber.fetch()
    await polling_drift_client.account_subscriber.fetch()

    await drift_client.update_perp_market_oracle(0, other_oracle, OracleSource.Pyth())  # type: ignore

    await asyncio.sleep(20)

    perp_oracle_price_before = (
        polling_drift_client.get_oracle_price_data_for_perp_market(0)
    ).price  # type: ignore
    print(f"perp_oracle_price_before: {perp_oracle_price_before}")
    assert perp_oracle_price_before == 30 * PRICE_PRECISION

    await asyncio.sleep(10)

    perp_oracle_price_after = (
        polling_drift_client.get_oracle_price_data_for_perp_market(0)
    ).price  # type: ignore
    print(f"perp_oracle_price_after: {perp_oracle_price_after}")
    assert perp_oracle_price_after == 100 * PRICE_PRECISION

    await polling_drift_client.account_subscriber.fetch()

    await drift_client.update_spot_market_oracle(1, other_oracle, OracleSource.Pyth())  # type: ignore

    await asyncio.sleep(20)

    spot_oracle_price_before = (
        polling_drift_client.get_oracle_price_data_for_spot_market(1)
    ).price  # type: ignore
    print(f"spot_oracle_price_before: {spot_oracle_price_before}")
    assert spot_oracle_price_before == 30 * PRICE_PRECISION

    await asyncio.sleep(10)

    spot_oracle_price_after = (
        polling_drift_client.get_oracle_price_data_for_spot_market(1)
    ).price  # type: ignore
    print(f"spot_oracle_price_after: {spot_oracle_price_after}")
    assert spot_oracle_price_after == 100 * PRICE_PRECISION


@mark.asyncio
async def test_ws(
    drift_client: Admin,
    first_oracle: Pubkey,
    other_oracle: Pubkey,
    program: Program,
):
    await drift_client.update_spot_market_oracle(1, first_oracle, OracleSource.Pyth())  # type: ignore
    await drift_client.update_perp_market_oracle(0, first_oracle, OracleSource.Pyth())  # type: ignore

    oracle_infos = [OracleInfo(first_oracle, OracleSource.Pyth())]  # type: ignore
    ws_drift_client = DriftClient(
        program.provider.connection,
        program.provider.wallet,
        account_subscription=AccountSubscriptionConfig(
            "websocket", commitment=Commitment("processed")
        ),
        spot_market_indexes=[0, 1],
        perp_market_indexes=[0],
        oracle_infos=oracle_infos,
    )

    await ws_drift_client.subscribe()

    assert ws_drift_client.account_subscriber is not None
    assert drift_client.account_subscriber is not None
    assert isinstance(ws_drift_client.account_subscriber, WebsocketAccountSubscriber)

    assert ws_drift_client.account_subscriber.is_subscribed()
    print(first_oracle)
    print(other_oracle)

    await drift_client.update_perp_market_oracle(0, other_oracle, OracleSource.Pyth())  # type: ignore

    perp_oracle_price_before_result = (
        ws_drift_client.get_oracle_price_data_for_perp_market(0)
    )
    assert perp_oracle_price_before_result is not None
    perp_oracle_price_before = perp_oracle_price_before_result.price

    print(f"perp_oracle_price_before: {perp_oracle_price_before}")
    assert perp_oracle_price_before == 30 * PRICE_PRECISION

    tries = 0
    while tries < 50:
        perp_oracle_price_after_result = (
            ws_drift_client.get_oracle_price_data_for_perp_market(0)
        )
        assert perp_oracle_price_after_result is not None
        perp_oracle_price_after = perp_oracle_price_after_result.price
        print(f"perp_oracle_price_after: {perp_oracle_price_after}")
        if perp_oracle_price_after == 100 * PRICE_PRECISION:
            break
        await asyncio.sleep(1)
        tries += 1

    if tries == 50:
        assert False

    await drift_client.update_spot_market_oracle(1, other_oracle, OracleSource.Pyth())  # type: ignore

    spot_oracle_price_before_result = (
        ws_drift_client.get_oracle_price_data_for_spot_market(1)
    )
    assert spot_oracle_price_before_result is not None
    spot_oracle_price_before = spot_oracle_price_before_result.price
    print(f"spot_oracle_price_before: {spot_oracle_price_before}")
    assert spot_oracle_price_before == 30 * PRICE_PRECISION

    tries = 0
    while tries < 50:
        spot_oracle_price_after_result = (
            ws_drift_client.get_oracle_price_data_for_spot_market(1)
        )
        assert spot_oracle_price_after_result is not None
        spot_oracle_price_after = spot_oracle_price_after_result.price
        print(f"spot_oracle_price_after: {spot_oracle_price_after}")
        if spot_oracle_price_after == 100 * PRICE_PRECISION:
            break
        await asyncio.sleep(1)
        tries += 1

    if tries == 50:
        assert False
