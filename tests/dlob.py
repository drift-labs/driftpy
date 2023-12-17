from dataclasses import dataclass
from typing import Optional
from driftpy.constants.numeric_constants import BASE_PRECISION
from driftpy.dlob.dlob import DLOB
from dlob_test_constants import mock_perp_markets, mock_spot_markets
from driftpy.types import MarketType, OraclePriceData, OrderType, PositionDirection
from solders.keypair import Keypair

from dlob_test_helpers import insert_order_to_dlob

@dataclass
class TestCase:
    expected_idx: int
    is_vamm: bool
    order_id: Optional[int]
    price: Optional[int]
    direction: Optional[PositionDirection]
    order_type: Optional[OrderType]
    slot: Optional[int]
    post_only: bool

def test_fresh_dlob_is_empty():
    dlob = DLOB()
    v_ask = 11
    v_bid = 10
    slot = 12

    oracle_price_data = OraclePriceData((v_bid + v_ask) // 2, slot, 1, 1, 1, True)

    # check perps
    for market in mock_perp_markets:
        found_asks = 0
        for _ in dlob.get_asks(market.market_index, slot, MarketType.Perp(), oracle_price_data, v_ask):
            found_asks += 1
        assert found_asks == 1

        found_bids = 0
        for _ in dlob.get_bids(market.market_index, 0, MarketType.Perp(), oracle_price_data, v_bid):
            found_bids += 1
        assert found_bids == 1

    # check spot
        for market in mock_spot_markets:
            found_asks = 0
            for _ in dlob.get_asks(market.market_index, slot, MarketType.Spot(), oracle_price_data, None):
                found_asks += 1
            assert found_asks == 0

            found_bids = 0
            for _ in dlob.get_bids(market.market_index, 0, MarketType.Spot(), oracle_price_data, None):
                found_bids += 1
            assert found_bids == 0

def test_clear_dlob():
    dlob = DLOB()
    v_ask = 15
    v_bid = 10

    user0 = Keypair()
    user1 = Keypair()
    user2 = Keypair()

    market_index = 0
    slot = 12
    oracle_price_data = OraclePriceData((v_bid + v_ask) // 2, slot, 1, 1, 1, True)

    insert_order_to_dlob(
        dlob,
        user0.pubkey,
        OrderType.Limit(),
        MarketType.Perp(),
        0,
        market_index,
        9,
        BASE_PRECISION,
        PositionDirection.Long(),
        v_bid,
        v_ask
    )

    insert_order_to_dlob(
        dlob,
        user1.pubkey,
        OrderType.Limit(),
        MarketType.Perp(),
        1,
        market_index,
        8,
        BASE_PRECISION,
        PositionDirection.Long(),
        v_bid,
        v_ask
    )

    insert_order_to_dlob(
        dlob,
        user2.pubkey,
        OrderType.Limit(),
        MarketType.Perp(),
        2,
        market_index,
        8,
        BASE_PRECISION,
        PositionDirection.Long(),
        v_bid,
        v_ask
    )

    bids = 0
    for _ in dlob.get_bids(market_index, slot, MarketType.Perp(), oracle_price_data, None):
        bids += 1
    assert bids == 3

    dlob.clear()

    cleared_bids = dlob.get_bids(market_index, slot, MarketType.Perp(), oracle_price_data, None)
    try:
        next(cleared_bids)
        no_bids = False
    except StopIteration:
        no_bids = True
    assert no_bids, 'bid generator should be done' 

def test_update_resting_limit_orders_bids():
    dlob = DLOB()
    v_ask = 15
    v_bid = 10
    
    slot = 1

    oracle_price_data = OraclePriceData((v_bid + v_ask) // 2, slot, 1, 1, 1, True)

    user0 = Keypair()
    user1 = Keypair()
    user2 = Keypair()

    market_index = 0
    market_type = MarketType.Perp()

    insert_order_to_dlob(
        dlob,
        user0.pubkey(),
        OrderType.Limit(),
        market_type,
        1,
        market_index,
        11,
        BASE_PRECISION,
        PositionDirection.Long(),
        v_bid,
        v_ask,
        1
    )

    insert_order_to_dlob(
        dlob,
        user1.pubkey(),
        OrderType.Limit(),
        market_type,
        2,
        market_index,
        12,
        BASE_PRECISION,
        PositionDirection.Long(),
        v_bid,
        v_ask,
        11
    )

    insert_order_to_dlob(
        dlob,
        user2.pubkey(),
        OrderType.Limit(),
        market_type,
        3,
        market_index,
        13,
        BASE_PRECISION,
        PositionDirection.Long(),
        v_bid,
        v_ask,
        21
    )

    taking_bids = list(dlob.get_taking_bids(market_index, market_type, slot, oracle_price_data))
    assert len(taking_bids) == 3
    assert taking_bids[0].order.order_id == 1
    assert taking_bids[1].order.order_id == 2
    assert taking_bids[2].order.order_id == 3

    resting_bids = list(dlob.get_resting_limit_bids(market_index, slot, market_type, oracle_price_data))
    assert len(resting_bids) == 0

    slot += 11

    taking_bids = list(dlob.get_taking_bids(market_index, market_type, slot, oracle_price_data))
    assert len(taking_bids) == 2
    assert taking_bids[0].order.order_id == 2
    assert taking_bids[1].order.order_id == 3

    resting_bids = list(dlob.get_resting_limit_bids(market_index, slot, market_type, oracle_price_data))
    assert len(resting_bids) == 1
    assert resting_bids[0].order.order_id == 1

    slot += 11

    taking_bids = list(dlob.get_taking_bids(market_index, market_type, slot, oracle_price_data))
    assert len(taking_bids) == 1
    assert taking_bids[0].order.order_id == 3

    resting_bids = list(dlob.get_resting_limit_bids(market_index, slot, market_type, oracle_price_data))
    assert len(resting_bids) == 2
    assert resting_bids[0].order.order_id == 2
    assert resting_bids[1].order.order_id == 1

    slot += 11

    taking_bids = list(dlob.get_taking_bids(market_index, market_type, slot, oracle_price_data))
    assert len(taking_bids) == 0

    resting_bids = list(dlob.get_resting_limit_bids(market_index, slot, market_type, oracle_price_data))
    assert len(resting_bids) == 3
    assert resting_bids[0].order.order_id == 3
    assert resting_bids[1].order.order_id == 2
    assert resting_bids[2].order.order_id == 1



    