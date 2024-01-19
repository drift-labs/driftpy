import copy
import pytest
from driftpy.constants.numeric_constants import (
    BASE_PRECISION,
    PEG_PRECISION,
    PRICE_PRECISION,
    QUOTE_PRECISION,
)
from driftpy.dlob.orderbook_levels import get_vamm_l2_generator
from driftpy.math.amm import calculate_market_open_bid_ask, calculate_updated_amm
from driftpy.types import OraclePriceData
from dlob_test_constants import mock_perp_markets


@pytest.mark.asyncio
async def test_orderbook_l2_gen_no_top_of_book_quote_amounts_10_num_orders_low_liq():
    print()
    mock_perps = copy.deepcopy(mock_perp_markets)

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
        has_sufficient_number_of_datapoints=True,
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
    mock_perps = copy.deepcopy(mock_perp_markets)

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
        has_sufficient_number_of_datapoints=True,
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
    assert total_bid_size == open_bids

    asks = list(generator[1]())
    total_ask_size = sum(order.size for order in asks)
    print(f"total_ask_size: {total_ask_size} \nopen_asks: {open_asks}")
    assert total_ask_size - abs(open_asks) <= 5


@pytest.mark.asyncio
async def test_orderbook_l2_gen_4_top_of_book_quote_amounts_10_num_orders():
    print()
    mock_perps = copy.deepcopy(mock_perp_markets)
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
        has_sufficient_number_of_datapoints=True,
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
    assert total_bid_size == open_bids

    asks = list(generator[1]())
    total_ask_size = sum(order.size for order in asks)
    print(f"total_ask_size: {total_ask_size} \nopen_asks: {open_asks}")
    assert total_ask_size - abs(open_asks) <= 5


@pytest.mark.asyncio
async def test_orderbook_l2_gen_4_top_quote_amounts_10_orders_low_bid_liquidity():
    print()
    mock_perps = copy.deepcopy(mock_perp_markets)
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
        has_sufficient_number_of_datapoints=True,
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
    assert total_bid_size == open_bids

    asks = list(generator[1]())
    total_ask_size = sum(order.size for order in asks)
    print(f"total_ask_size: {total_ask_size} \nopen_asks: {open_asks}")
    assert total_ask_size - abs(open_asks) <= 5


@pytest.mark.asyncio
async def test_orderbook_l2_gen_4_top_quote_amounts_10_orders_low_ask_liquidity():
    print()
    mock_perps = copy.deepcopy(mock_perp_markets)
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
        has_sufficient_number_of_datapoints=True,
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
    mock_perps = copy.deepcopy(mock_perp_markets)
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
        has_sufficient_number_of_datapoints=True,
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
