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

workspace = workspace_fixture("protocol-v2", scope="function")

MANTISSA_SQRT_SCALE = int(sqrt(PRICE_PRECISION))
AMM_INITIAL_BAA = (5 * 10**13) * MANTISSA_SQRT_SCALE
AMM_INITIAL_QAA = (5 * 10**13) * MANTISSA_SQRT_SCALE
USDC_AMOUNT = 10 * QUOTE_PRECISION


@fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@async_fixture(scope="function")
async def usdc_mint(provider: Provider):
    return await _create_mint(provider)


@async_fixture(scope="function")
async def user_usdc_account(
    usdc_mint: Keypair,
    provider: Provider,
):
    return await _create_and_mint_user_usdc(
        usdc_mint, provider, USDC_AMOUNT * 2, provider.wallet.public_key
    )


@fixture(scope="function")
def program(workspace: WorkspaceType) -> Program:
    """Create a Program instance."""
    return workspace["drift"]


@fixture(scope="function")
def provider(program: Program) -> Provider:
    return program.provider


@async_fixture(scope="function")
async def admin_client(program: Program, usdc_mint: Keypair) -> Admin:
    market_indexes = [0, 1]
    spot_market_indexes = [0, 1, 2]

    admin = Admin(
        program.provider.connection,
        program.provider.wallet,
        account_subscription=AccountSubscriptionConfig("websocket"),
        perp_market_indexes=market_indexes,
        spot_market_indexes=spot_market_indexes,
    )
    await admin.initialize(usdc_mint.pubkey(), admin_controls_prices=True)
    await admin.subscribe()
    return admin


@async_fixture(scope="function")
async def sol_oracle(workspace: WorkspaceType):
    oracle_program = workspace["pyth"]
    oracle = await mock_oracle(oracle_program, 3, -7)
    return oracle


@async_fixture(scope="function")
async def setup_markets(admin_client: Admin, usdc_mint: Keypair, sol_oracle: Pubkey):
    # Initialize markets
    await admin_client.initialize_spot_market(usdc_mint.pubkey())

    # Initialize SOL spot markets with different oracle sources
    mint = await _create_mint(admin_client.program.provider)
    await initialize_sol_spot_market(
        admin_client,
        sol_oracle,
        mint.pubkey(),
        oracle_source=OracleSource.Pyth(),  # type: ignore
    )
    await initialize_sol_spot_market(
        admin_client,
        sol_oracle,
        mint.pubkey(),
        oracle_source=OracleSource.Pyth1K(),  # type: ignore
    )

    # Initialize perp markets
    await admin_client.initialize_perp_market(
        0,
        sol_oracle,
        AMM_INITIAL_BAA,
        AMM_INITIAL_QAA,
        0,
        3 * PEG_PRECISION,
        oracle_source=OracleSource.Pyth(),  # type: ignore
    )
    await admin_client.initialize_perp_market(
        1,
        sol_oracle,
        AMM_INITIAL_BAA,
        AMM_INITIAL_QAA,
        0,
        3000 * PEG_PRECISION,
        oracle_source=OracleSource.Pyth1K(),  # type: ignore
    )


@mark.asyncio
async def test_polling(
    program: Program, admin_client: Admin, sol_oracle: Pubkey, setup_markets
):
    oracle_infos = [
        OracleInfo(sol_oracle, OracleSource.Pyth()),  # type: ignore
        OracleInfo(sol_oracle, OracleSource.Pyth1K()),  # type: ignore
    ]

    polling_client = DriftClient(
        program.provider.connection,
        program.provider.wallet,
        account_subscription=AccountSubscriptionConfig(
            "polling",
            bulk_account_loader=BulkAccountLoader(program.provider.connection),
        ),
        spot_market_indexes=[0, 1, 2],
        perp_market_indexes=[0, 1],
        oracle_infos=oracle_infos,
    )
    await polling_client.subscribe()
    print("sub done")

    # Verify spot market oracles
    oracle_data_for_spot_market_1 = (
        polling_client.get_oracle_price_data_for_spot_market(1)
    )
    assert oracle_data_for_spot_market_1 is not None
    spot_price_1 = oracle_data_for_spot_market_1.price
    assert spot_price_1 == 3 * PRICE_PRECISION

    oracle_data_for_spot_market_2 = (
        polling_client.get_oracle_price_data_for_spot_market(2)
    )
    assert oracle_data_for_spot_market_2 is not None
    spot_price_2 = oracle_data_for_spot_market_2.price
    assert spot_price_2 == 3000 * PRICE_PRECISION

    # Verify perp market oracles
    oracle_data_for_perp_market_0 = (
        polling_client.get_oracle_price_data_for_perp_market(0)
    )
    assert oracle_data_for_perp_market_0 is not None
    perp_price_0 = oracle_data_for_perp_market_0.price
    assert perp_price_0 == 3 * PRICE_PRECISION

    oracle_data_for_perp_market_1 = (
        polling_client.get_oracle_price_data_for_perp_market(1)
    )
    assert oracle_data_for_perp_market_1 is not None
    perp_price_1 = oracle_data_for_perp_market_1.price
    assert perp_price_1 == 3000 * PRICE_PRECISION


@mark.asyncio
async def test_ws(
    program: Program, admin_client: Admin, sol_oracle: Pubkey, setup_markets
):
    oracle_infos = [
        OracleInfo(sol_oracle, OracleSource.Pyth()),  # type: ignore
        OracleInfo(sol_oracle, OracleSource.Pyth1K()),  # type: ignore
    ]

    ws_client = DriftClient(
        program.provider.connection,
        program.provider.wallet,
        account_subscription=AccountSubscriptionConfig(
            "websocket", commitment=Commitment("processed")
        ),
        spot_market_indexes=[0, 1, 2],
        perp_market_indexes=[0, 1],
        oracle_infos=oracle_infos,
    )
    await ws_client.subscribe()

    # Verify spot market oracles
    oracle_data_for_spot_market_1 = ws_client.get_oracle_price_data_for_spot_market(1)
    assert oracle_data_for_spot_market_1 is not None
    spot_price_1 = oracle_data_for_spot_market_1.price
    assert spot_price_1 == 3 * PRICE_PRECISION

    oracle_data_for_spot_market_2 = ws_client.get_oracle_price_data_for_spot_market(2)
    assert oracle_data_for_spot_market_2 is not None
    spot_price_2 = oracle_data_for_spot_market_2.price
    assert spot_price_2 == 3000 * PRICE_PRECISION

    # Verify perp market oracles
    oracle_data_for_perp_market_0 = ws_client.get_oracle_price_data_for_perp_market(0)
    assert oracle_data_for_perp_market_0 is not None
    perp_price_0 = oracle_data_for_perp_market_0.price
    assert perp_price_0 == 3 * PRICE_PRECISION

    oracle_data_for_perp_market_1 = ws_client.get_oracle_price_data_for_perp_market(1)
    assert oracle_data_for_perp_market_1 is not None
    perp_price_1 = oracle_data_for_perp_market_1.price
    assert perp_price_1 == 3000 * PRICE_PRECISION
