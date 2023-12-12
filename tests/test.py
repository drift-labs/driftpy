import asyncio

from pytest import fixture, mark
from pytest_asyncio import fixture as async_fixture
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from anchorpy import Program, Provider, WorkspaceType, workspace_fixture

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.admin import Admin
from driftpy.constants.numeric_constants import (
    PRICE_PRECISION,
    AMM_RESERVE_PRECISION,
    BASE_PRECISION,
    QUOTE_PRECISION,
    SPOT_BALANCE_PRECISION,
    SPOT_WEIGHT_PRECISION,
)
from math import sqrt

from driftpy.drift_user import DriftUser
from driftpy.drift_client import DriftClient
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import UserMapConfig, PollingConfig, WebsocketConfig
from driftpy.events.event_subscriber import EventSubscriber
from driftpy.events.types import EventSubscriptionOptions, PollingLogProviderConfig
from driftpy.setup.helpers import (
    _create_mint,
    _create_and_mint_user_usdc,
    mock_oracle,
    set_price_feed,
    _airdrop_user,
)

from driftpy.addresses import *
from driftpy.types import (
    UserAccount,
    PositionDirection,
    OracleSource,
    PerpMarketAccount,
    OrderType,
    OrderParams,
    MarketType,
    is_variant,
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
    "protocol-v2", build_cmd="anchor build", scope="session"
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
async def event_subscriber(program: Program) -> EventSubscriber:
    event_subscriber = EventSubscriber(
        program.provider.connection,
        program,
        EventSubscriptionOptions(log_provider_config=PollingLogProviderConfig()),
    )
    event_subscriber.subscribe()
    return event_subscriber


@async_fixture(scope="session")
async def initialized_spot_market(
    drift_client: Admin,
    usdc_mint: Keypair,
):
    await drift_client.initialize_spot_market(usdc_mint.pubkey())


@mark.asyncio
async def test_initialized_spot_market_2(
    drift_client: Admin, initialized_spot_market, workspace: WorkspaceType
):
    admin_drift_client = drift_client
    oracle_price = 1
    oracle_program = workspace["pyth"]

    oracle = await mock_oracle(oracle_program, oracle_price, -7)
    mint = await _create_mint(admin_drift_client.program.provider)

    optimal_util = SPOT_WEIGHT_PRECISION // 2
    optimal_weight = int(SPOT_WEIGHT_PRECISION * 20)
    max_rate = int(SPOT_WEIGHT_PRECISION * 50)

    init_weight = int(SPOT_WEIGHT_PRECISION * 8 / 10)
    main_weight = int(SPOT_WEIGHT_PRECISION * 9 / 10)

    init_liab_weight = int(SPOT_WEIGHT_PRECISION * 12 / 10)
    main_liab_weight = int(SPOT_WEIGHT_PRECISION * 11 / 10)

    await admin_drift_client.initialize_spot_market(
        mint.pubkey(),
        oracle=oracle,
        optimal_utilization=optimal_util,
        optimal_rate=optimal_weight,
        max_rate=max_rate,
        oracle_source=OracleSource.Pyth(),
        initial_asset_weight=init_weight,
        maintenance_asset_weight=main_weight,
        initial_liability_weight=init_liab_weight,
        maintenance_liability_weight=main_liab_weight,
    )

    await drift_client.account_subscriber.update_cache()

    spot_market = await get_spot_market_account(admin_drift_client.program, 1)
    assert spot_market.market_index == 1
    print(spot_market.market_index)


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
    initialized_spot_market: Pubkey,
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
async def test_init_user(
    drift_client: Admin,
):
    await drift_client.initialize_user()
    await drift_client.get_user().account_subscriber.update_cache()
    user_public_key = get_user_account_public_key(
        drift_client.program.program_id, drift_client.authority, 0
    )
    user: UserAccount = await get_user_account(drift_client.program, user_public_key)
    assert user.authority == drift_client.authority


@mark.asyncio
async def test_usdc_deposit(
    drift_client: Admin,
    user_usdc_account: Keypair,
):
    usdc_spot_market = await get_spot_market_account(drift_client.program, 0)
    assert usdc_spot_market.market_index == 0
    await drift_client.deposit(
        USDC_AMOUNT, 0, user_usdc_account.pubkey(), user_initialized=True
    )
    await drift_client.get_user(0).account_subscriber.update_cache()
    user_account = drift_client.get_user(0).get_user_account()
    assert (
        user_account.spot_positions[0].scaled_balance
        == USDC_AMOUNT / QUOTE_PRECISION * SPOT_BALANCE_PRECISION
    )

@mark.asyncio

async def test_user_map_polling(drift_client: Admin, workspace):
    polling_config = PollingConfig('polling', 0.5)
    user_map_config = UserMapConfig(drift_client, polling_config)
    user_map = UserMap(user_map_config)
    await user_map.subscribe()

    assert user_map.is_subscribed == True

    user_account = drift_client.get_user(0)

    assert user_map.has(str(user_account.user_public_key))

    assert user_map.size() == 1

    throwaway = Pubkey.new_unique()
    
    await user_map.must_get(str(throwaway))
    
    assert user_map.size() == 2
    assert user_map.has(str(throwaway))
    
    await user_map.unsubscribe()

    assert user_map.is_subscribed == False

@mark.asyncio
async def test_user_map_ws(drift_client: Admin, workspace):
    ws_config = WebsocketConfig('websocket')
    user_map_config = UserMapConfig(drift_client, ws_config)
    user_map = UserMap(user_map_config)
    await user_map.subscribe()

    assert user_map.is_subscribed == True

    user_account = drift_client.get_user(0)

    assert user_map.has(str(user_account.user_public_key))

    assert user_map.size() == 1

    throwaway = Pubkey.new_unique()
    
    await user_map.must_get(str(throwaway))
    
    assert user_map.size() == 2
    assert user_map.has(str(throwaway))

    await user_map.unsubscribe()

    assert user_map.is_subscribed == False

@mark.asyncio
async def test_open_orders(
    drift_client: Admin,
):
    drift_user = DriftUser(
        drift_client,
        account_subscription=AccountSubscriptionConfig("cached"),
    )
    await drift_user.subscribe()
    user_account = drift_client.get_user(0).get_user_account()

    assert len(user_account.orders) == 32

    open_orders = drift_user.get_open_orders()
    assert len(open_orders) == 0

    order_params = OrderParams(
        market_type=MarketType.Perp(),
        order_type=OrderType.Market(),
        market_index=0,
        base_asset_amount=int(1 * BASE_PRECISION),
        direction=PositionDirection.Long(),
        user_order_id=169,
    )
    ixs = drift_client.get_place_orders_ix([order_params])
    await drift_client.send_ixs(ixs)
    await drift_user.account_subscriber.update_cache()
    open_orders_after = drift_user.get_open_orders()
    assert open_orders_after[0].base_asset_amount == BASE_PRECISION
    assert open_orders_after[0].order_id == 1
    assert open_orders_after[0].user_order_id == 169

    await drift_client.get_user().account_subscriber.update_cache()
    await drift_client.cancel_order(1, 0)
    await drift_user.account_subscriber.update_cache()
    open_orders_after2 = drift_user.get_open_orders()
    assert len(open_orders_after2) == 0


@mark.asyncio
async def test_update_curve(
    workspace,
    drift_client: Admin,
):
    market = await get_perp_market_account(drift_client.program, 0)
    new_sqrt_k = int(market.amm.sqrt_k * 1.05)
    await drift_client.update_k(new_sqrt_k, 0)
    market = await get_perp_market_account(drift_client.program, 0)
    assert market.amm.sqrt_k == new_sqrt_k

    from driftpy.setup.helpers import set_price_feed_detailed

    pyth_program = workspace["pyth"]
    slot = (await drift_client.program.provider.connection.get_slot()).value
    await set_price_feed_detailed(pyth_program, market.amm.oracle, 1.07, 0, slot)

    new_peg = int(market.amm.peg_multiplier * 1.05)
    await drift_client.repeg_curve(new_peg, 0)
    market = await get_perp_market_account(drift_client.program, 0)
    assert market.amm.peg_multiplier == new_peg


@mark.asyncio
async def test_add_remove_liquidity(
    drift_client: Admin,
):
    market = await get_perp_market_account(drift_client.program, 0)
    n_shares = market.amm.order_step_size

    await drift_client.update_lp_cooldown_time(0)
    state = await get_state_account(drift_client.program)
    assert state.lp_cooldown_time == 0

    await drift_client.add_liquidity(n_shares, 0)
    await drift_client.get_user(0).account_subscriber.update_cache()
    user_account = drift_client.get_user(0).get_user_account()
    assert user_account.perp_positions[0].lp_shares == n_shares

    await drift_client.settle_lp(drift_client.get_user_account_public_key(), 0)

    await drift_client.remove_liquidity(n_shares, 0)
    await drift_client.get_user(0).account_subscriber.update_cache()
    user_account = drift_client.get_user(0).get_user_account()
    assert user_account.perp_positions[0].lp_shares == 0


@mark.asyncio
async def test_update_amm(drift_client: Admin, workspace):
    market = await get_perp_market_account(drift_client.program, 0)
    # provider: Provider = drift_client.program.provider

    # pyth_program = workspace["pyth"]
    # await set_price_feed(pyth_program, market.amm.oracle, 1.5)
    # signer2 = pyth_program.provider.wallet.payer
    # ix1 = await get_set_price_feed_detailed_ix(
    #     pyth_program, market.amm.oracle, 1, 0, 1
    # )

    ix2 = drift_client.get_update_amm_ix([0])
    ixs = [ix2]

    # ixs = [ix1, ix2]

    await drift_client.send_ixs(ixs)
    market_after = await get_perp_market_account(drift_client.program, 0)
    assert market.amm.last_update_slot != market_after.amm.last_update_slot


@mark.asyncio
async def test_open_close_position(
    drift_client: Admin, event_subscriber: EventSubscriber
):
    await drift_client.update_perp_auction_duration(0)

    baa = 10 * AMM_RESERVE_PRECISION
    sig = await drift_client.open_position(
        PositionDirection.Long(),
        baa,
        0,
    )

    while True:
        events = event_subscriber.get_events_by_tx(str(sig))
        if events is not None:
            assert events[0].event_type == "OrderActionRecord"
            assert events[0].data.base_asset_amount_filled is None
            assert is_variant(events[0].data.action, "Place")
            assert events[1].event_type == "OrderRecord"
            assert events[1].data.order.base_asset_amount == baa
            assert events[2].event_type == "OrderActionRecord"
            assert events[2].data.base_asset_amount_filled == baa
            assert is_variant(events[2].data.action, "Fill")
            break
        await asyncio.sleep(1)

    from solana.rpc.commitment import Confirmed, Processed

    drift_client.program.provider.connection._commitment = Confirmed
    await drift_client.program.provider.connection.get_transaction(sig)
    drift_client.program.provider.connection._commitment = Processed
    # print(tx)

    await drift_client.get_user(0).account_subscriber.update_cache()
    user_account = drift_client.get_user(0).get_user_account()

    assert user_account.perp_positions[0].base_asset_amount == baa
    assert user_account.perp_positions[0].quote_asset_amount < 0

    await drift_client.close_position(0)

    await drift_client.get_user(0).account_subscriber.update_cache()
    user_account = drift_client.get_user(0).get_user_account()
    assert user_account.perp_positions[0].base_asset_amount == 0
    assert user_account.perp_positions[0].quote_asset_amount < 0


@mark.asyncio
async def test_stake_if(
    drift_client: Admin,
    user_usdc_account: Keypair,
):
    # important
    drift_client.usdc_ata = user_usdc_account.pubkey()

    await drift_client.update_update_insurance_fund_unstaking_period(0, 0)

    await drift_client.initialize_insurance_fund_stake(0)
    if_acc = await get_if_stake_account(drift_client.program, drift_client.authority, 0)
    assert if_acc.market_index == 0

    await drift_client.add_insurance_fund_stake(
        0, 1 * QUOTE_PRECISION, user_usdc_account.pubkey()
    )

    user_stats = await get_user_stats_account(
        drift_client.program, drift_client.authority
    )
    assert user_stats.if_staked_quote_asset_amount == 1 * QUOTE_PRECISION

    await drift_client.request_remove_insurance_fund_stake(0, 1 * QUOTE_PRECISION)

    await drift_client.remove_insurance_fund_stake(0, user_usdc_account.pubkey())

    user_stats = await get_user_stats_account(
        drift_client.program, drift_client.authority
    )
    assert user_stats.if_staked_quote_asset_amount == 0

# note this goes at end bc the main clearing house loses all collateral ...
@mark.asyncio
async def test_liq_perp(
    drift_client: Admin, usdc_mint: Keypair, workspace: WorkspaceType
):
    market = await get_perp_market_account(drift_client.program, 0)
    user_account = drift_client.get_user(0).get_user_account()

    liq, _ = await _airdrop_user(drift_client.program.provider)
    liq_drift_client = DriftClient(
        drift_client.program.provider.connection,
        liq,
        account_subscription=AccountSubscriptionConfig("cached"),
    )
    await liq_drift_client.subscribe()
    usdc_acc = await _create_and_mint_user_usdc(
        usdc_mint, drift_client.program.provider, USDC_AMOUNT, liq.pubkey()
    )
    await liq_drift_client.initialize_user()
    await liq_drift_client.add_user(0)
    await liq_drift_client.get_user(0).account_subscriber.update_cache()
    await liq_drift_client.deposit(
        USDC_AMOUNT,
        0,
        usdc_acc.pubkey(),
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
    await drift_client.open_position(
        PositionDirection.Short(),
        int(baa),
        0,
    )

    # liq em
    pyth_program = workspace["pyth"]
    await set_price_feed(pyth_program, market.amm.oracle, 1.5)

    await liq_drift_client.liquidate_perp(drift_client.authority, 0, int(baa) // 10)

    # liq takes on position
    await liq_drift_client.get_user(0).account_subscriber.update_cache()
    position = liq_drift_client.get_perp_position(0)
    assert position.base_asset_amount != 0