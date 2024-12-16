import asyncio
import math
from pathlib import Path

from anchorpy.program.core import Program
from anchorpy.provider import Provider, Wallet
from anchorpy.pytest_plugin import workspace_fixture
from anchorpy.workspace import WorkspaceType
from icecream import ic
from pytest import fixture, mark
from pytest_asyncio import fixture as async_fixture
from solana.rpc.commitment import Commitment
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.accounts.bulk_account_loader import BulkAccountLoader
from driftpy.accounts.test_bulk_account_loader import TestBulkAccountLoader
from driftpy.admin import Admin
from driftpy.constants.numeric_constants import (
    PEG_PRECISION,
    PRICE_PRECISION,
)
from driftpy.drift_client import DriftClient
from driftpy.events.event_subscriber import EventSubscriber
from driftpy.setup.helpers import (
    _create_and_mint_user_usdc,
    _create_mint,
    create_funded_keypair,
    initialize_quote_spot_market,
    initialize_sol_spot_market,
    mock_oracle_no_program,
)
from driftpy.test_client import TestClient
from driftpy.types import OracleInfo, OracleSource

PATH = Path("protocol-v2")
USDC_AMOUNT = 10 * 10**6
LARGE_USDC_AMOUNT = 10_000 * 10**6

MANTISSA_SQRT_SCALE = int(math.sqrt(PRICE_PRECISION))
AMM_INITIAL_QUOTE_ASSET_RESERVE = (5 * 10**13) * MANTISSA_SQRT_SCALE
AMM_INITIAL_BASE_ASSET_RESERVE = (5 * 10**13) * MANTISSA_SQRT_SCALE

workspace = workspace_fixture("protocol-v2", scope="session", build_cmd="")


@fixture(scope="session")
def event_loop():
    """This must absolutely not be async fixture, it must be a normal fixture"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@fixture(scope="session")
def program(workspace: WorkspaceType) -> Program:
    return workspace["drift"]


@fixture(scope="session")
def provider(program: Program) -> Provider:
    return program.provider


@async_fixture(scope="session")
async def event_subscriber(provider: Provider, program: Program):
    event_subscriber = EventSubscriber(provider.connection, program)
    event_subscriber.subscribe()
    return event_subscriber


@fixture(scope="session")
def account_loader(
    provider: Provider, event_subscriber: EventSubscriber
) -> BulkAccountLoader:
    ic(event_subscriber)
    loader = TestBulkAccountLoader(provider.connection, Commitment("confirmed"), 1)
    ic(loader)
    return loader


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


@async_fixture(scope="session")
async def sol_oracle(provider: Provider):
    return await mock_oracle_no_program(provider.connection, provider.wallet, 3)


@fixture(scope="session")
def perp_market_indexes() -> list[int]:
    return [0, 1]


@fixture(scope="session")
def spot_market_indexes() -> list[int]:
    return [0, 1, 2]


@fixture(scope="session")
def oracle_infos(sol_oracle: Pubkey) -> list[OracleInfo]:
    return [
        OracleInfo(
            pubkey=sol_oracle,
            source=OracleSource.Pyth(),  # type: ignore
        ),
        OracleInfo(
            pubkey=sol_oracle,
            source=OracleSource.Pyth1K(),  # type: ignore
        ),
    ]


@async_fixture(scope="session")
async def drift_client(
    program: Program,
    perp_market_indexes: list[int],
    spot_market_indexes: list[int],
    oracle_infos: list[OracleInfo],
    account_loader: BulkAccountLoader,
) -> Admin:
    ic("Creating drift client")
    admin = TestClient(
        program.provider.connection,
        program.provider.wallet,
        env=None,
        account_subscription=AccountSubscriptionConfig(
            "polling",
            bulk_account_loader=account_loader,
        ),
        perp_market_indexes=perp_market_indexes,
        spot_market_indexes=spot_market_indexes,
        oracle_infos=oracle_infos,
    )
    return admin


@async_fixture(scope="session")
async def initialized_drift_client(
    drift_client: Admin,
    usdc_mint: Keypair,
    sol_oracle: Pubkey,
):
    await drift_client.initialize(
        usdc_mint=usdc_mint.pubkey(),
        admin_controls_prices=True,
    )
    await drift_client.subscribe()
    await initialize_quote_spot_market(drift_client, usdc_mint.pubkey())

    await initialize_sol_spot_market(
        drift_client,
        sol_oracle,
        oracle_source=OracleSource.Pyth(),  # type: ignore
    )
    await initialize_sol_spot_market(
        drift_client,
        sol_oracle,
        oracle_source=OracleSource.Pyth1K(),  # type: ignore
    )

    periodicity = 0
    await drift_client.initialize_perp_market(
        market_index=0,
        price_oracle=sol_oracle,
        base_asset_reserve=AMM_INITIAL_BASE_ASSET_RESERVE,
        quote_asset_reserve=AMM_INITIAL_QUOTE_ASSET_RESERVE,
        periodicity=periodicity,
        peg_multiplier=3 * PEG_PRECISION,
        oracle_source=OracleSource.Pyth(),  # type: ignore
    )

    await drift_client.initialize_perp_market(
        market_index=1,
        price_oracle=sol_oracle,
        base_asset_reserve=AMM_INITIAL_BASE_ASSET_RESERVE,
        quote_asset_reserve=AMM_INITIAL_QUOTE_ASSET_RESERVE,
        periodicity=periodicity,
        peg_multiplier=3000 * PEG_PRECISION,
        oracle_source=OracleSource.Pyth1K(),  # type: ignore
    )

    return drift_client


@mark.asyncio
async def test_polling(
    initialized_drift_client: Admin,  # We need this to create everything
    usdc_mint: Keypair,
    sol_oracle: Pubkey,
    account_loader: TestBulkAccountLoader,
    provider: Provider,
    perp_market_indexes: list[int],
    spot_market_indexes: list[int],
    oracle_infos: list[OracleInfo],
) -> None:
    ic("Begin test")

    user_keypair = await create_funded_keypair(provider)
    drift_client = TestClient(
        connection=provider.connection,
        wallet=Wallet(user_keypair),
        perp_market_indexes=perp_market_indexes,
        spot_market_indexes=spot_market_indexes,
        oracle_infos=oracle_infos,
        account_subscription=AccountSubscriptionConfig(
            "polling", bulk_account_loader=account_loader
        ),
        market_lookup_table=None,
        env=None,
    )
    await drift_client.subscribe()
    await drift_client.initialize_user()

    spot_market_account = drift_client.get_spot_market_account(1)
    ic(spot_market_account)
    assert spot_market_account is not None


@mark.asyncio
async def test_websocket(
    initialized_drift_client: Admin,  # We need this to create everything
    usdc_mint: Keypair,
    sol_oracle: Pubkey,
    provider: Provider,
    perp_market_indexes: list[int],
    spot_market_indexes: list[int],
    oracle_infos: list[OracleInfo],
) -> None:
    ic("Begin test")

    user_keypair = await create_funded_keypair(provider)
    drift_client = DriftClient(
        connection=provider.connection,
        wallet=Wallet(user_keypair),
        perp_market_indexes=perp_market_indexes,
        spot_market_indexes=spot_market_indexes,
        oracle_infos=oracle_infos,
        account_subscription=AccountSubscriptionConfig("websocket"),
    )
    await drift_client.subscribe()

    normal_price = drift_client.get_oracle_price_data_for_spot_market(1)
    one_k_price = drift_client.get_oracle_price_data_for_spot_market(2)

    assert normal_price is not None
    assert one_k_price is not None
    assert normal_price.price == PRICE_PRECISION * 3
    assert one_k_price.price == PRICE_PRECISION * 3000

    normal_perp_price = drift_client.get_oracle_price_data_for_perp_market(0)
    assert normal_perp_price is not None
    assert normal_perp_price.price == PRICE_PRECISION * 3

    one_k_perp_price = drift_client.get_oracle_price_data_for_perp_market(1)
    assert one_k_perp_price is not None
    assert one_k_perp_price.price == PRICE_PRECISION * 3000

    await drift_client.unsubscribe()
