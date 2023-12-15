from driftpy.math.auction import get_auction_price, is_auction_complete
from driftpy.types import OraclePriceData, Order, PositionDirection, is_variant


def get_limit_price(order: Order, oracle_price_data: OraclePriceData, slot: int, fallback_price) -> int:
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
        (order.auction.start_price) != 0 or order.auction_end_price != 0

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