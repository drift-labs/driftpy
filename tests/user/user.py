from pytest import mark
from copy import deepcopy

from driftpy.constants.numeric_constants import *
from driftpy.math.margin import MarginCategory
from driftpy.math.perp_position import calculate_position_pnl

from dlob_test_constants import mock_perp_markets, mock_spot_markets
from driftpy.math.spot_position import get_worst_case_token_amounts
from driftpy.oracles.strict_oracle_price import StrictOraclePrice
from helpers import make_mock_user, mock_user_account


@mark.asyncio
async def test_empty():
    user = await make_mock_user(
        mock_perp_markets,
        mock_spot_markets,
        mock_user_account,
        [1, 1, 1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1, 1, 1],
    )
    ua = user.get_user_account()

    assert not ua.idle
    assert user.get_free_collateral() == 0
    assert user.get_health() == 100
    assert user.get_max_leverage_for_perp(0) == 0


@mark.asyncio
async def test_unsettled_pnl():
    # no collateral, but positive upnl no liability
    perp_markets = deepcopy(mock_perp_markets)
    spot_markets = deepcopy(mock_spot_markets)
    user_account = deepcopy(mock_user_account)

    user_account.perp_positions[0].base_asset_amount = 0 * BASE_PRECISION
    user_account.perp_positions[0].quote_asset_amount = 10 * QUOTE_PRECISION

    assert user_account.perp_positions[0].quote_asset_amount == 10_000_000

    user = await make_mock_user(
        perp_markets,
        spot_markets,
        user_account,
        [1, 1, 1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1, 1, 1],
    )
    ua = user.get_user_account()

    assert not ua.idle

    active_perps = user.get_active_perp_positions()
    assert len(active_perps) == 1
    assert ua.perp_positions[0].quote_asset_amount == 10_000_000
    assert user.get_free_collateral() == 0

    quote_price = user.drift_client.get_oracle_price_data_for_spot_market(0).price
    assert quote_price == 1_000_000

    pnl_1 = calculate_position_pnl(
        perp_markets[0],
        active_perps[0],
        user.drift_client.get_oracle_price_data_for_spot_market(0),
        False,
    )
    assert pnl_1 == 10_000_000

    upnl = user.get_unrealized_pnl()
    assert upnl == 10_000_000

    liq = user.can_be_liquidated()
    assert not liq

    assert user.get_health() == 100
    assert user.get_max_leverage_for_perp(0) == 0


@mark.asyncio
async def test_liquidatable_long():
    # no collateral, positive upnl with liab
    perp_markets = deepcopy(mock_perp_markets)
    spot_markets = deepcopy(mock_spot_markets)
    user_account = deepcopy(mock_user_account)

    user_account.perp_positions[0].base_asset_amount = 20 * BASE_PRECISION
    user_account.perp_positions[0].quote_asset_amount = -10 * QUOTE_PRECISION

    user = await make_mock_user(
        perp_markets,
        spot_markets,
        user_account,
        [1, 1, 1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1, 1, 1],
    )
    ua = user.get_user_account()

    assert not ua.idle

    assert user.get_free_collateral() == 0
    assert user.get_unrealized_pnl(True, 0) == 10_000_000

    liq = user.can_be_liquidated()
    assert liq

    assert user.get_health() == 0
    assert user.get_max_leverage_for_perp(0) == 20_000


@mark.asyncio
async def test_large_usdc():
    # no collateral, positive upnl with liab
    perp_markets = deepcopy(mock_perp_markets)
    spot_markets = deepcopy(mock_spot_markets)
    user_account = deepcopy(mock_user_account)

    perp_markets[0].imf_factor = 550
    user_account.spot_positions[0].scaled_balance = 10_000 * SPOT_BALANCE_PRECISION

    user = await make_mock_user(
        perp_markets,
        spot_markets,
        user_account,
        [1, 1, 1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1, 1, 1],
    )
    ua = user.get_user_account()

    assert not ua.idle

    assert ua.perp_positions[0].base_asset_amount == 0
    assert ua.perp_positions[0].quote_asset_amount == 0
    assert len(user.get_active_perp_positions()) == 0

    assert ua.spot_positions[0].scaled_balance == 10_000 * SPOT_BALANCE_PRECISION

    for i in range(1, 8):
        assert ua.spot_positions[i].scaled_balance == 0

    expected_amount = 10_000_000_000
    assert user.get_token_amount(0) == expected_amount
    assert user.get_net_spot_market_value(None) == expected_amount
    assert user.get_spot_market_asset_and_liability_value()[1] == 0
    assert user.get_free_collateral() > 0

    assert user.get_unrealized_pnl(True, 0) == 0

    liq = user.can_be_liquidated()
    assert not liq

    assert user.get_health() == 100

    # TODO: these fail
    # assert user.get_max_leverage_for_perp(0) == 50_000
    # assert user.get_max_leverage_for_perp(0, MarginCategory.MAINTENANCE) == 100_000


@mark.asyncio
async def test_worst_case_token_amt():
    user_account = deepcopy(mock_user_account)
    sol_market = deepcopy(mock_spot_markets[1])


@mark.asyncio
async def test_sol_spot_custom_mrgn_ratio():
    user_account = deepcopy(mock_user_account)
    sol_market = deepcopy(mock_spot_markets[1])

    sol_market.initial_asset_weight = 8_000
    sol_market.initial_liability_weight = 12_000
    sol_market.cumulative_deposit_interest = SPOT_CUMULATIVE_INTEREST_PRECISION
    sol_market.cumulative_borrow_interest = SPOT_CUMULATIVE_INTEREST_PRECISION

    strict_oracle_price = StrictOraclePrice(PRICE_PRECISION * 25, None)

    spot_position = user_account.spot_positions[1]
    spot_position.market_index = 1
    spot_position.open_bids = 100 * 10e9

    worst_case_before = get_worst_case_token_amounts(
        spot_position,
        sol_market,
        strict_oracle_price,
        MarginCategory.INITIAL,
        user_account.max_margin_ratio,
    )

    assert worst_case_before.weight == 8_000

    # change max margin ratio
    user_account.max_margin_ratio = MARGIN_PRECISION

    worst_case_after = get_worst_case_token_amounts(
        spot_position,
        sol_market,
        strict_oracle_price,
        MarginCategory.INITIAL,
        user_account.max_margin_ratio,
    )

    assert worst_case_after.weight == 0


@mark.asyncio
async def test_sol_perp_custom_mrgn_ratio():
    perp_markets = deepcopy(mock_perp_markets)
    spot_markets = deepcopy(mock_spot_markets)
    user_account = deepcopy(mock_user_account)

    perp_markets[0].margin_ratio_initial = 2_000
    perp_markets[0].margin_ratio_maintenance = 1_000

    spot_markets[0].initial_asset_weight = 1_000
    spot_markets[0].initial_liability_weight = 1_000

    user_account.spot_positions[0].scaled_balance = 10_000 * SPOT_BALANCE_PRECISION

    user = await make_mock_user(
        perp_markets,
        spot_markets,
        user_account,
        [1, 1, 1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1, 1, 1],
    )

    assert user.get_token_amount(0) == 10_000_000_000
    assert user.get_net_spot_market_value(None) == 10_000_000_000
    assert user.get_spot_market_asset_and_liability_value()[1] == 0
    assert user.get_free_collateral() > 0

    i_lev = user.get_max_leverage_for_perp(0, MarginCategory.INITIAL)
    m_lev = user.get_max_leverage_for_perp(0, MarginCategory.MAINTENANCE)
    assert i_lev == 5_000
    assert m_lev == 10_000

    user_account.max_margin_ratio = MARGIN_PRECISION // 2

    user_2 = await make_mock_user(
        perp_markets,
        spot_markets,
        user_account,
        [1, 1, 1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1, 1, 1],
    )

    i_lev_2 = user_2.get_max_leverage_for_perp(0, MarginCategory.INITIAL)
    m_lev_2 = user_2.get_max_leverage_for_perp(0, MarginCategory.MAINTENANCE)
    assert i_lev_2 == 2_000
    assert m_lev_2 == 10_000
