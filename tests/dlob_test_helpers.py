from solders.pubkey import Pubkey

from typing import Optional
from driftpy.dlob.dlob import DLOB

from driftpy.types import MarketType, Order, OrderStatus, OrderTriggerCondition, OrderType, PositionDirection

def insert_order_to_dlob(
    dlob: DLOB,
    user_account: Pubkey,
    order_type: OrderType,
    market_type: MarketType,
    order_id: int,
    market_index: int,
    price: int,
    base_asset_amount: int,
    direction: PositionDirection,
    auction_start_price: int,
    auction_end_price: int,
    slot: Optional[int] = None,
    max_ts = 0,
    oracle_price_offset = 0,
    post_only = False,
    auction_duration = 10
):
    slot = slot if slot is not None else 1
    order = Order(
        slot, 
        price, 
        base_asset_amount, 
        0, 
        0, 
        0, 
        auction_start_price, 
        auction_end_price, 
        max_ts, 
        oracle_price_offset, 
        order_id, 
        market_index,
        OrderStatus.Open(),
        order_type,
        market_type,
        0,
        PositionDirection.Long(),
        direction,
        False,
        post_only,
        False,
        OrderTriggerCondition.Above(),
        auction_duration,
        [0, 0, 0]
    )
    dlob.insert_order(order, user_account, slot)
