from typing import Optional
from driftpy.math.auction import get_auction_price, is_auction_complete
from driftpy.types import OraclePriceData, Order, PositionDirection, is_one_of_variant, is_variant


def get_limit_price(order: Order, oracle_price_data: OraclePriceData, slot: int, fallback_price: Optional[int] = None) -> int:
    if has_auction_price(order, slot):
        limit_price = get_auction_price(order, slot, oracle_price_data.price)
    elif order.oracle_price_offset != 0:
        limit_price = oracle_price_data.price + order.oracle_price_offset
    elif order.price == 0:
        limit_price = fallback_price
    else:
        limit_price = order.price

    return limit_price
    

def has_auction_price(order: Order, slot: int) -> bool:
    return not is_auction_complete(order, slot) and \
        (order.auction_start_price != 0 or order.auction_end_price != 0)


def standardize_price(price: int, tick_size: int, direction: PositionDirection) -> int:
    if price == 0:
        print('price is zero')
        return price
    
    remainder = price % tick_size
    if remainder == 0:
        return price
    
    if is_variant(direction, "Long"):
        return price - remainder
    else:
        return price + tick_size - remainder
    
def is_market_order(order: Order) -> bool:
    return is_one_of_variant(order.order_type, ['Market', 'TriggerMarket', 'Oracle'])

def is_limit_order(order: Order) -> bool:
    return is_one_of_variant(order.order_type, ['Limit', 'TriggerLimit'])

def must_be_triggered(order: Order) -> bool:
    return is_one_of_variant(order.order_type, ['TriggerMarket', 'TriggerLimit'])

def is_triggered(order: Order) -> bool:
    return is_one_of_variant(order.trigger_condition, ['TriggeredAbove', 'TriggeredBelow'])

def is_resting_limit_order(order: Order, slot: int) -> bool:
    if not is_limit_order(order):
        return False
    
    if is_variant(order.order_type, 'TriggerLimit'):
        if is_variant(order.direction, 'Long') and order.trigger_price < order.price:
            return False
        elif is_variant(order.direction, 'Short') and order.trigger_price > order.price:
            return False
        
        return is_auction_complete(order, slot)
    
    return order.post_only or is_auction_complete(order, slot)

def is_order_expired(order: Order, ts: int, enforce_buffer: bool = False) -> bool:
    if must_be_triggered(order) or not is_variant(order.status, 'Open') or order.max_ts == 0:
        return False
    
    if enforce_buffer and is_limit_order(order):
        max_ts = order.max_ts + 15
    else:
        max_ts = order.max_ts

    return ts > max_ts

def is_taking_order(order: Order, slot: int) -> bool:
    return is_market_order(order) or not is_resting_limit_order(order, slot)