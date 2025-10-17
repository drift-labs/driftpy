import copy
from copy import deepcopy
from unittest.mock import Mock

import pytest

from driftpy.constants.numeric_constants import (
    BASE_PRECISION,
    PEG_PRECISION,
    PRICE_PRECISION,
    QUOTE_PRECISION,
    SPOT_MARKET_CUMULATIVE_INTEREST_PRECISION,
    SPOT_MARKET_WEIGHT_PRECISION,
)
from driftpy.dlob.orderbook_levels import get_vamm_l2_generator
from driftpy.math.amm import calculate_market_open_bid_ask, calculate_updated_amm
from driftpy.types import (
    AssetTier,
    MarketStatus,
    OraclePriceData,
    OracleSource,
    PerpMarketAccount,
    SpotMarketAccount,
)
from tests.dlob_test_constants import devnet_spot_market_configs, mock_perp_markets

# Create a mock object for Pubkey
mock_pubkey = Mock()
mock_historical_oracle_data = Mock()
mock_historical_index_data = Mock()
mock_revenue_pool = Mock()
mock_spot_fee_pool = Mock()
mock_insurance_fund = Mock()

mock_spot_markets = [
    SpotMarketAccount(
        status=MarketStatus.Active(),
        asset_tier=AssetTier.COLLATERAL,
        name=[],
        max_token_deposits=1000000 * QUOTE_PRECISION,
        market_index=0,
        pubkey=mock_pubkey,  # Use mock object
        mint=devnet_spot_market_configs[0].mint,  # Replace with actual mint
        vault=mock_pubkey,  # Use mock object
        oracle=mock_pubkey,  # Use mock object
        historical_oracle_data=mock_historical_oracle_data,
        historical_index_data=mock_historical_index_data,
        revenue_pool=mock_revenue_pool,
        spot_fee_pool=mock_spot_fee_pool,
        insurance_fund=mock_insurance_fund,
        total_spot_fee=0,
        deposit_balance=0,
        borrow_balance=0,
        cumulative_deposit_interest=SPOT_MARKET_CUMULATIVE_INTEREST_PRECISION,
        cumulative_borrow_interest=SPOT_MARKET_CUMULATIVE_INTEREST_PRECISION,
        total_social_loss=0,
        total_quote_social_loss=0,
        withdraw_guard_threshold=0,
        deposit_token_twap=0,
        borrow_token_twap=0,
        utilization_twap=0,
        last_interest_ts=0,
        last_twap_ts=0,
        expiry_ts=0,
        order_step_size=0,
        order_tick_size=0,
        min_order_size=0,
        max_position_size=0,
        next_fill_record_id=0,
        next_deposit_record_id=0,
        initial_asset_weight=SPOT_MARKET_WEIGHT_PRECISION,
        maintenance_asset_weight=SPOT_MARKET_WEIGHT_PRECISION,
        initial_liability_weight=SPOT_MARKET_WEIGHT_PRECISION,
        maintenance_liability_weight=SPOT_MARKET_WEIGHT_PRECISION,
        imf_factor=0,
        liquidator_fee=0,
        if_liquidation_fee=0,
        optimal_utilization=0,
        optimal_borrow_rate=0,
        max_borrow_rate=0,
        decimals=6,
        orders_enabled=True,
        oracle_source=OracleSource.Pyth(),
        paused_operations=0,
        if_paused_operations=0,
        fee_adjustment=0,
        max_token_borrows_fraction=0,
    ),
    # ... other SpotMarketAccount instances ...
]


def custom_deepcopy_perp_market_account(perp_market_account):
    # Manually copy each attribute, handling Pubkey separately
    return PerpMarketAccount(
        status=deepcopy(perp_market_account.status),
        name=deepcopy(perp_market_account.name),
        contract_type=deepcopy(perp_market_account.contract_type),
        contract_tier=deepcopy(perp_market_account.contract_tier),
        expiry_ts=perp_market_account.expiry_ts,
        expiry_price=perp_market_account.expiry_price,
        market_index=perp_market_account.market_index,
        pubkey=perp_market_account.pubkey,  # Directly assign or use a mock
        amm=deepcopy(perp_market_account.amm),
        number_of_users_with_base=perp_market_account.number_of_users_with_base,
        number_of_users=perp_market_account.number_of_users,
        margin_ratio_initial=perp_market_account.margin_ratio_initial,
        margin_ratio_maintenance=perp_market_account.margin_ratio_maintenance,
        next_fill_record_id=perp_market_account.next_fill_record_id,
        pnl_pool=deepcopy(perp_market_account.pnl_pool),
        if_liquidation_fee=perp_market_account.if_liquidation_fee,
        liquidator_fee=perp_market_account.liquidator_fee,
        imf_factor=perp_market_account.imf_factor,
        next_funding_rate_record_id=perp_market_account.next_funding_rate_record_id,
        next_curve_record_id=perp_market_account.next_curve_record_id,
        unrealized_pnl_imf_factor=perp_market_account.unrealized_pnl_imf_factor,
        unrealized_pnl_max_imbalance=perp_market_account.unrealized_pnl_max_imbalance,
        unrealized_pnl_initial_asset_weight=perp_market_account.unrealized_pnl_initial_asset_weight,
        unrealized_pnl_maintenance_asset_weight=perp_market_account.unrealized_pnl_maintenance_asset_weight,
        insurance_claim=deepcopy(perp_market_account.insurance_claim),
        paused_operations=perp_market_account.paused_operations,
        quote_spot_market_index=perp_market_account.quote_spot_market_index,
        fee_adjustment=perp_market_account.fee_adjustment,
        fuel_boost_taker=perp_market_account.fuel_boost_taker,
        fuel_boost_maker=perp_market_account.fuel_boost_maker,
        fuel_boost_position=perp_market_account.fuel_boost_position,
        high_leverage_margin_ratio_initial=perp_market_account.high_leverage_margin_ratio_initial,
        high_leverage_margin_ratio_maintenance=perp_market_account.high_leverage_margin_ratio_maintenance,
        pool_id=perp_market_account.pool_id,
        padding=deepcopy(perp_market_account.padding),
    )


@pytest.mark.asyncio
async def test_orderbook_l2_gen_no_top_of_book_quote_amounts_10_num_orders_low_liq():
    print()
    mock_perps = [
        custom_deepcopy_perp_market_account(market) for market in mock_perp_markets
    ]

    mock_1 = mock_perps[0]
    cc = 38_104_569
    mock_1.amm.base_asset_reserve = cc * BASE_PRECISION
    mock_1.amm.max_base_asset_reserve = mock_1.amm.base_asset_reserve + 1_234_835
    mock_1.amm.min_base_asset_reserve = mock_1.amm.base_asset_reserve - BASE_PRECISION
    mock_1.amm.quote_asset_reserve = cc * BASE_PRECISION
    mock_1.amm.peg_multiplier = int(18.32 * PEG_PRECISION)

    now = 1_688_881_915

    oracle_price_data = OraclePriceData(
        price=int(18.624 * PRICE_PRECISION),
        slot=0,
        confidence=1,
        twap=1,
        twap_confidence=1,
        has_sufficient_number_of_data_points=True,
    )

    mock_1.amm.historical_oracle_data.last_oracle_price = int(18.5535 * PRICE_PRECISION)

    updated_amm = calculate_updated_amm(mock_1.amm, oracle_price_data)

    open_bids, open_asks = calculate_market_open_bid_ask(
        updated_amm.base_asset_reserve,
        updated_amm.min_base_asset_reserve,
        updated_amm.max_base_asset_reserve,
        updated_amm.order_step_size,
    )

    generator = get_vamm_l2_generator(
        market_account=mock_1,
        oracle_price_data=oracle_price_data,
        num_orders=10,
        now=now,
        top_of_book_quote_amounts=[],
    )

    bids = list(generator[0]())

    total_bid_size = sum(order.size for order in bids)

    print(f"total_bid_size: {total_bid_size} \n" f"open_bids: {open_bids}")

    assert abs(total_bid_size - open_bids) < 10  # low error
    assert total_bid_size - open_bids < 0  # under est

    asks = list(generator[1]())

    total_ask_size = sum(order.size for order in asks)

    print(f"total_ask_size: {total_ask_size} \n" f"open_asks: {open_asks}")

    assert total_ask_size - abs(open_asks) < 5  # small rounding errors


@pytest.mark.asyncio
async def test_orderbook_l2_gen_no_top_of_book_quote_amounts_10_num_orders():
    print()
    mock_perps = [
        custom_deepcopy_perp_market_account(market) for market in mock_perp_markets
    ]

    mock_1 = mock_perps[0]
    cc = 38_104_569
    mock_1.amm.base_asset_reserve = cc * BASE_PRECISION
    mock_1.amm.max_base_asset_reserve = mock_1.amm.base_asset_reserve * 2
    mock_1.amm.min_base_asset_reserve = mock_1.amm.base_asset_reserve // 2
    mock_1.amm.quote_asset_reserve = cc * BASE_PRECISION
    mock_1.amm.peg_multiplier = int(18.32 * PEG_PRECISION)

    now = 1_688_881_915

    oracle_price_data = OraclePriceData(
        price=int(18.624 * PRICE_PRECISION),
        slot=0,
        confidence=1,
        twap=1,
        twap_confidence=1,
        has_sufficient_number_of_data_points=True,
    )
    mock_1.amm.historical_oracle_data.last_oracle_price = int(18.5535 * PRICE_PRECISION)

    updated_amm = calculate_updated_amm(mock_1.amm, oracle_price_data)

    open_bids, open_asks = calculate_market_open_bid_ask(
        updated_amm.base_asset_reserve,
        updated_amm.min_base_asset_reserve,
        updated_amm.max_base_asset_reserve,
        updated_amm.order_step_size,
    )

    generator = get_vamm_l2_generator(
        market_account=mock_1,
        oracle_price_data=oracle_price_data,
        num_orders=10,
        now=now,
        top_of_book_quote_amounts=[],
    )

    bids = list(generator[0]())
    total_bid_size = sum(order.size for order in bids)
    print(f"total_bid_size: {total_bid_size} \nopen_bids: {open_bids}")
    assert (
        abs(int(total_bid_size) - open_bids) <= 10
    )  # Allow small precision difference

    asks = list(generator[1]())
    total_ask_size = sum(order.size for order in asks)
    print(f"total_ask_size: {total_ask_size} \nopen_asks: {open_asks}")
    assert total_ask_size - abs(open_asks) <= 5


@pytest.mark.asyncio
async def test_orderbook_l2_gen_4_top_of_book_quote_amounts_10_num_orders():
    print()
    mock_perps = [
        custom_deepcopy_perp_market_account(market) for market in mock_perp_markets
    ]
    mock_market1 = mock_perps[0]
    cc = 38_104_569
    mock_market1.amm.base_asset_reserve = cc * BASE_PRECISION
    mock_market1.amm.max_base_asset_reserve = mock_market1.amm.base_asset_reserve * 2
    mock_market1.amm.min_base_asset_reserve = mock_market1.amm.base_asset_reserve // 2
    mock_market1.amm.quote_asset_reserve = cc * BASE_PRECISION
    mock_market1.amm.peg_multiplier = int(18.32 * PEG_PRECISION)
    mock_market1.amm.sqrt_k = cc * BASE_PRECISION

    now = 1_688_881_915

    oracle_price_data = OraclePriceData(
        price=int(18.624 * PRICE_PRECISION),
        slot=0,
        confidence=1,
        twap=1,
        twap_confidence=1,
        has_sufficient_number_of_data_points=True,
    )
    mock_market1.amm.historical_oracle_data.last_oracle_price = int(
        18.5535 * PRICE_PRECISION
    )

    updated_amm = calculate_updated_amm(mock_market1.amm, oracle_price_data)

    open_bids, open_asks = calculate_market_open_bid_ask(
        updated_amm.base_asset_reserve,
        updated_amm.min_base_asset_reserve,
        updated_amm.max_base_asset_reserve,
        updated_amm.order_step_size,
    )

    assert open_bids != open_asks

    top_of_book_quote_amounts = [
        10 * QUOTE_PRECISION,
        100 * QUOTE_PRECISION,
        1000 * QUOTE_PRECISION,
        10000 * QUOTE_PRECISION,
    ]

    generator = get_vamm_l2_generator(
        market_account=mock_market1,
        oracle_price_data=oracle_price_data,
        num_orders=10,
        now=now,
        top_of_book_quote_amounts=top_of_book_quote_amounts,
    )

    bids = list(generator[0]())
    total_bid_size = sum(order.size for order in bids)
    print(f"total_bid_size: {total_bid_size} \nopen_bids: {open_bids}")
    assert (
        abs(int(total_bid_size) - open_bids) <= 10
    )  # Allow small precision difference

    asks = list(generator[1]())
    total_ask_size = sum(order.size for order in asks)
    print(f"total_ask_size: {total_ask_size} \nopen_asks: {open_asks}")
    assert total_ask_size - abs(open_asks) <= 5


@pytest.mark.asyncio
async def test_orderbook_l2_gen_4_top_quote_amounts_10_orders_low_bid_liquidity():
    print()
    mock_perps = [
        custom_deepcopy_perp_market_account(market) for market in mock_perp_markets
    ]
    mock_market1 = mock_perps[0]
    cc = 38_104_569
    mock_market1.amm.base_asset_reserve = cc * BASE_PRECISION
    mock_market1.amm.max_base_asset_reserve = (
        mock_market1.amm.base_asset_reserve + BASE_PRECISION
    )  # only 1 base
    mock_market1.amm.min_base_asset_reserve = mock_market1.amm.base_asset_reserve // 2
    mock_market1.amm.quote_asset_reserve = cc * BASE_PRECISION
    mock_market1.amm.peg_multiplier = int(18.32 * PEG_PRECISION)
    mock_market1.amm.sqrt_k = cc * BASE_PRECISION

    now = 1_688_881_915

    oracle_price_data = OraclePriceData(
        price=int(18.624 * PRICE_PRECISION),
        slot=0,
        confidence=1,
        twap=1,
        twap_confidence=1,
        has_sufficient_number_of_data_points=True,
    )
    mock_market1.amm.historical_oracle_data.last_oracle_price = int(
        18.5535 * PRICE_PRECISION
    )

    updated_amm = calculate_updated_amm(mock_market1.amm, oracle_price_data)

    open_bids, open_asks = calculate_market_open_bid_ask(
        updated_amm.base_asset_reserve,
        updated_amm.min_base_asset_reserve,
        updated_amm.max_base_asset_reserve,
        updated_amm.order_step_size,
    )

    assert open_bids != open_asks

    top_of_book_quote_amounts = [
        10 * QUOTE_PRECISION,
        100 * QUOTE_PRECISION,
        1000 * QUOTE_PRECISION,
        10000 * QUOTE_PRECISION,
    ]

    generator = get_vamm_l2_generator(
        market_account=mock_market1,
        oracle_price_data=oracle_price_data,
        num_orders=10,
        now=now,
        top_of_book_quote_amounts=top_of_book_quote_amounts,
    )

    bids = list(generator[0]())
    total_bid_size = sum(order.size for order in bids)
    print(f"total_bid_size: {total_bid_size} \nopen_bids: {open_bids}")
    assert (
        abs(int(total_bid_size) - open_bids) <= 10
    )  # Allow small precision difference

    asks = list(generator[1]())
    total_ask_size = sum(order.size for order in asks)
    print(f"total_ask_size: {total_ask_size} \nopen_asks: {open_asks}")
    assert total_ask_size - abs(open_asks) <= 5


@pytest.mark.asyncio
async def test_orderbook_l2_gen_4_top_quote_amounts_10_orders_low_ask_liquidity():
    print()
    mock_perps = [
        custom_deepcopy_perp_market_account(market) for market in mock_perp_markets
    ]
    mock_market1 = mock_perps[0]
    cc = 38_104_569
    mock_market1.amm.base_asset_reserve = cc * BASE_PRECISION
    mock_market1.amm.max_base_asset_reserve = (
        mock_market1.amm.base_asset_reserve + BASE_PRECISION * 1000
    )  # 1000 base
    mock_market1.amm.min_base_asset_reserve = mock_market1.amm.base_asset_reserve - (
        BASE_PRECISION // 2
    )  # only .5 base
    mock_market1.amm.quote_asset_reserve = cc * BASE_PRECISION
    mock_market1.amm.peg_multiplier = int(18.32 * PEG_PRECISION)
    mock_market1.amm.sqrt_k = cc * BASE_PRECISION

    now = 1_688_881_915

    oracle_price_data = OraclePriceData(
        price=int(18.624 * PRICE_PRECISION),
        slot=0,
        confidence=1,
        twap=1,
        twap_confidence=1,
        has_sufficient_number_of_data_points=True,
    )
    mock_market1.amm.historical_oracle_data.last_oracle_price = int(
        18.5535 * PRICE_PRECISION
    )

    updated_amm = calculate_updated_amm(mock_market1.amm, oracle_price_data)

    open_bids, open_asks = calculate_market_open_bid_ask(
        updated_amm.base_asset_reserve,
        updated_amm.min_base_asset_reserve,
        updated_amm.max_base_asset_reserve,
        updated_amm.order_step_size,
    )

    assert open_bids != open_asks

    top_of_book_quote_amounts = [
        10 * QUOTE_PRECISION,
        100 * QUOTE_PRECISION,
        1000 * QUOTE_PRECISION,
        10000 * QUOTE_PRECISION,
    ]

    generator = get_vamm_l2_generator(
        market_account=mock_market1,
        oracle_price_data=oracle_price_data,
        num_orders=10,
        now=now,
        top_of_book_quote_amounts=top_of_book_quote_amounts,
    )

    bids = list(generator[0]())
    total_bid_size = sum(order.size for order in bids)
    print(f"total_bid_size: {total_bid_size} \nopen_bids: {open_bids}")
    assert abs(total_bid_size - open_bids) < 5

    asks = list(generator[1]())
    assert len(asks) == 1
    for ask in asks:
        print(ask.size)
    total_ask_size = sum(order.size for order in asks)
    print(f"total_ask_size: {total_ask_size} \nopen_asks: {open_asks}")
    assert total_ask_size - abs(open_asks) <= 5


@pytest.mark.asyncio
async def test_orderbook_l2_gen_no_top_of_book_quote_amounts_10_orders_no_liquidity():
    print()
    mock_perps = [
        custom_deepcopy_perp_market_account(market) for market in mock_perp_markets
    ]
    mock_market1 = mock_perps[0]
    cc = 38_104_569
    mock_market1.amm.base_asset_reserve = cc * BASE_PRECISION
    mock_market1.amm.min_order_size = 5
    mock_market1.amm.max_base_asset_reserve = mock_market1.amm.base_asset_reserve + 9
    mock_market1.amm.min_base_asset_reserve = mock_market1.amm.base_asset_reserve - 9
    mock_market1.amm.quote_asset_reserve = cc * BASE_PRECISION
    mock_market1.amm.peg_multiplier = int(18.32 * PEG_PRECISION)
    mock_market1.amm.sqrt_k = cc * BASE_PRECISION

    now = 1_688_881_915

    oracle_price_data = OraclePriceData(
        price=int(18.624 * PRICE_PRECISION),
        slot=0,
        confidence=1,
        twap=1,
        twap_confidence=1,
        has_sufficient_number_of_data_points=True,
    )
    mock_market1.amm.historical_oracle_data.last_oracle_price = int(
        18.5535 * PRICE_PRECISION
    )

    updated_amm = calculate_updated_amm(mock_market1.amm, oracle_price_data)

    open_bids, open_asks = calculate_market_open_bid_ask(
        updated_amm.base_asset_reserve,
        updated_amm.min_base_asset_reserve,
        updated_amm.max_base_asset_reserve,
        updated_amm.order_step_size,
    )

    generator = get_vamm_l2_generator(
        market_account=mock_market1,
        oracle_price_data=oracle_price_data,
        num_orders=10,
        now=now,
        top_of_book_quote_amounts=[],
    )

    bids = list(generator[0]())
    total_bid_size = sum(order.size for order in bids)
    print(f"total_bid_size: {total_bid_size} \nopen_bids: {open_bids}")
    assert open_bids == 9
    assert total_bid_size == 0

    asks = list(generator[1]())
    total_ask_size = sum(order.size for order in asks)
    print(f"total_ask_size: {total_ask_size} \nopen_asks: {open_asks}")
    assert open_asks == -9
    assert total_ask_size == 0
