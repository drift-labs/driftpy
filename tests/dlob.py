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


# GENERAL DLOB TESTS
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

def test_update_resting_limit_order_asks():
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
        13,
        BASE_PRECISION,
        PositionDirection.Short(),
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
        PositionDirection.Short(),
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
        11,
        BASE_PRECISION,
        PositionDirection.Short(),
        v_bid,
        v_ask,
        21
    )

    taking_asks = list(dlob.get_taking_asks(market_index, market_type, slot, oracle_price_data))
    assert len(taking_asks) == 3
    assert taking_asks[0].order.order_id == 1
    assert taking_asks[1].order.order_id == 2
    assert taking_asks[2].order.order_id == 3

    resting_asks = list(dlob.get_resting_limit_asks(market_index, slot, market_type, oracle_price_data))
    assert len(resting_asks) == 0

    slot += 11

    taking_asks = list(dlob.get_taking_asks(market_index, market_type, slot, oracle_price_data))
    assert len(taking_asks) == 2
    assert taking_asks[0].order.order_id == 2
    assert taking_asks[1].order.order_id == 3

    resting_asks = list(dlob.get_resting_limit_asks(market_index, slot, market_type, oracle_price_data))
    assert len(resting_asks) == 1
    assert resting_asks[0].order.order_id == 1

    slot += 11

    taking_asks = list(dlob.get_taking_asks(market_index, market_type, slot, oracle_price_data))
    assert len(taking_asks) == 1
    assert taking_asks[0].order.order_id == 3

    resting_asks = list(dlob.get_resting_limit_asks(market_index, slot, market_type, oracle_price_data))
    assert len(resting_asks) == 2
    assert resting_asks[0].order.order_id == 2
    assert resting_asks[1].order.order_id == 1

    slot += 11

    taking_asks = list(dlob.get_taking_asks(market_index, market_type, slot, oracle_price_data))
    assert len(taking_asks) == 0

    resting_asks = list(dlob.get_resting_limit_asks(market_index, slot, market_type, oracle_price_data))
    assert len(resting_asks) == 3
    assert resting_asks[0].order.order_id == 3
    assert resting_asks[1].order.order_id == 2
    assert resting_asks[2].order.order_id == 1

# DLOB PERP MARKET TESTS
def test_dlob_proper_bids_perp():
    dlob = DLOB()
    v_ask = 15
    v_bid = 10
    market_index = 0
    
    slot = 12

    oracle_price_data = OraclePriceData((v_bid + v_ask) // 2, slot, 1, 1, 1, True)

    testcases = [
        TestCase(0, False, 5, 0, PositionDirection.Long(), OrderType.Market(), 0, False),
        TestCase(1, False, 6, 0, PositionDirection.Long(), OrderType.Market(), 1, False),
        TestCase(2, False, 7, 0, PositionDirection.Long(), OrderType.Market(), 2, False),
        TestCase(3, False, 1, 12, PositionDirection.Long(), OrderType.Limit(), 3, False),
        TestCase(4, False, 2, 11, PositionDirection.Long(), OrderType.Limit(), 4, False),
        TestCase(7, False, 3, 8, PositionDirection.Long(), OrderType.Limit(), 5, True),
        TestCase(5, True, None, None, None, None, None, False),
        TestCase(6, False, 4, 9, PositionDirection.Long(), OrderType.Limit(), 6, True)
    ]

    for t in testcases:
        if t.is_vamm:
            continue

        user = Keypair()

        insert_order_to_dlob(
            dlob,
            user.pubkey(),
            t.order_type or OrderType.Limit(),
            MarketType.Perp(),
            t.order_id or 0,
            market_index,
            t.price or 0,
            BASE_PRECISION,
            t.direction or PositionDirection.Long(),
            0 if t.post_only else v_bid,
            0 if t.post_only else v_ask,
            t.slot,
            post_only = t.post_only 
        )

    expected_testcases = sorted(testcases, key=lambda tc: tc.expected_idx)

    all_bids = dlob.get_bids(market_index, slot, MarketType.Perp(), oracle_price_data, v_bid)

    count_bids = 0
    print()
    for bid in all_bids:
        assert bid.is_vamm_node() == expected_testcases[count_bids].is_vamm, 'expected vamm node'
        
        if bid.order:
            assert bid.order.order_id == expected_testcases[count_bids].order_id, 'expected order_id'
            assert bid.order.price == expected_testcases[count_bids].price, 'expected price'
            assert str(bid.order.direction) == str(expected_testcases[count_bids].direction), 'expected direction'
            assert str(bid.order.order_type) == str(expected_testcases[count_bids].order_type), 'expected order type'
        count_bids += 1
    assert len(testcases) == count_bids, "expected count"

    taking_bids = dlob.get_taking_bids(market_index, MarketType.Perp(), slot, oracle_price_data)
    count_bids = 0
    expected_testcases_slice = expected_testcases[:5]
    for bid in taking_bids:
        assert bid.is_vamm_node() == expected_testcases_slice[count_bids].is_vamm, "expected vAMM node"
        if bid.order:
            assert bid.order.order_id == expected_testcases_slice[count_bids].order_id, "expected orderId"
            assert bid.order.price == expected_testcases_slice[count_bids].price, "expected price"
            assert bid.order.direction == expected_testcases_slice[count_bids].direction, "expected order direction"
            assert bid.order.order_type == expected_testcases_slice[count_bids].order_type, "expected order type"
        count_bids += 1

    assert count_bids == len(expected_testcases_slice), "expected count"

    limit_bids = dlob.get_resting_limit_bids(market_index, slot, MarketType.Perp(), oracle_price_data)
    count_bids = 0
    # I don't think we really care about the vAMM node, plus resting limit bids won't give it to us
    # So we will not include it in these assertions
    expected_testcases_slice = expected_testcases[6:]
    for bid in limit_bids:
        assert bid.is_vamm_node() == expected_testcases_slice[count_bids].is_vamm, "expected vAMM node"
        if bid.order:
            assert bid.order.order_id == expected_testcases_slice[count_bids].order_id, "expected orderId"
            assert bid.order.price == expected_testcases_slice[count_bids].price, "expected price"
            assert bid.order.direction == expected_testcases_slice[count_bids].direction, "expected order direction"
            assert bid.order.order_type == expected_testcases_slice[count_bids].order_type, "expected order type"
        count_bids += 1

    assert count_bids == len(expected_testcases_slice), "expected count"

def test_dlob_proper_asks_perp():
    dlob = DLOB()
    v_ask = 15
    v_bid = 10
    market_index = 0

    slot = 12
    oracle_price_data = OraclePriceData((v_bid + v_ask) // 2, slot, 1, 1, 1, True)

    testcases = [
        TestCase(0, False, 3, 0, PositionDirection.Short(), OrderType.Market(), 0, False),
        TestCase(1, False, 4, 0, PositionDirection.Short(), OrderType.Market(), 1, False),
        TestCase(2, False, 5, 0, PositionDirection.Short(), OrderType.Market(), 2, False),
        TestCase(3, False, 1, 13, PositionDirection.Short(), OrderType.Limit(), 3, False),
        TestCase(6, False, 6, 16, PositionDirection.Short(), OrderType.Limit(), 4, True),
        TestCase(4, True, None, None, None, None, 0, False),
        TestCase(7, False, 7, 17, PositionDirection.Short(), OrderType.Limit(), 4, True),
        TestCase(5, False, 2, 14, PositionDirection.Short(), OrderType.Limit(), 4, True)
    ]

    for t in testcases:
        if t.is_vamm:
            continue

        user = Keypair()

        insert_order_to_dlob(
            dlob,
            user.pubkey(),
            t.order_type or OrderType.Limit(),
            MarketType.Perp(),
            t.order_id or 0,
            market_index,
            t.price or 0,
            BASE_PRECISION,
            t.direction or PositionDirection.Short(),
            0 if t.post_only else v_bid,
            0 if t.post_only else v_ask,
            t.slot,
            post_only = t.post_only
        )

    expected_testcases = sorted(testcases, key=lambda tc: tc.expected_idx)

    taking_asks = dlob.get_taking_asks(market_index, MarketType.Perp(), slot, oracle_price_data)
    count_asks = 0
    expected_testcases_slice = expected_testcases[:4]
    for ask in taking_asks:
        assert ask.is_vamm_node() == expected_testcases_slice[count_asks].is_vamm, "expected vAMM node"
        if ask.order:
            assert ask.order.order_id == expected_testcases_slice[count_asks].order_id, "expected orderId"
            assert ask.order.price == expected_testcases_slice[count_asks].price, "expected price"
            assert ask.order.direction == expected_testcases_slice[count_asks].direction, "expected order direction"
            assert ask.order.order_type == expected_testcases_slice[count_asks].order_type, "expected order type"
        count_asks += 1

    assert count_asks == len(expected_testcases_slice), "expected count"
    
    limit_asks = dlob.get_resting_limit_asks(market_index, slot, MarketType.Perp(),oracle_price_data)
    count_asks = 0
    expected_testcases_slice = expected_testcases[5:]
    for ask in limit_asks:
        assert ask.is_vamm_node() == expected_testcases_slice[count_asks].is_vamm, "expected vAMM node"
        if ask.order:
            assert ask.order.order_id == expected_testcases_slice[count_asks].order_id, "expected orderId"
            assert ask.order.price == expected_testcases_slice[count_asks].price, "expected price"
            assert ask.order.direction == expected_testcases_slice[count_asks].direction, "expected order direction"
            assert ask.order.order_type == expected_testcases_slice[count_asks].order_type, "expected order type"
        count_asks += 1

    assert count_asks == len(expected_testcases_slice), "expected count"
