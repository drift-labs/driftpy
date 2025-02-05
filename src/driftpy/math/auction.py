from typing import Tuple, Literal
from driftpy.types import Order, PositionDirection, is_one_of_variant, is_variant

MARKET_ORDERS = ["Market", "TriggerMarket", "Limit", "TriggerLimit"]

def is_auction_complete(order: Order, slot: int) -> bool:
    """
    Check if the auction is complete.

    Args:
    order (Order): The order object.
    slot (int): The current slot.

    Returns:
    bool: True if the auction is complete, False otherwise.
    """
    if order.auction_duration == 0:
        return True
    return slot - order.slot > order.auction_duration

def get_auction_price(order: Order, slot: int, oracle_price: int) -> int:
    """
    Get the auction price for an order.
    
    Args:
    order (Order): The order object.
    slot (int): The current slot.
    oracle_price (int): The current oracle price.
    
    Returns:
    int: The calculated auction price.
    
    Raises:
    ValueError: If the order type is not supported.
    """
    if is_one_of_variant(order.order_type, MARKET_ORDERS):
        return get_auction_price_for_fixed_auction(order, slot)
    elif is_variant(order.order_type, "Oracle"):
        return get_auction_price_for_oracle_offset_auction(order, slot, oracle_price)
    else:
        raise ValueError(f"Can't get auction price for order type: {order.order_type}")

def get_auction_price_for_fixed_auction(order: Order, slot: int) -> int:
    """
    Calculate the auction price for a fixed auction.
    
    Args:
    order (Order): The order object.
    slot (int): The current slot.
    
    Returns:
    int: The calculated auction price.
    """
    slots_elapsed = slot - order.slot
    delta_denominator = order.auction_duration
    delta_numerator = min(slots_elapsed, delta_denominator)

    if delta_denominator == 0:
        return order.auction_end_price

    direction_multiplier: Literal[1, -1] = 1 if is_variant(order.direction, "Long") else -1
    
    price_delta = direction_multiplier * (
        order.auction_start_price
        - order.auction_end_price
    ) * delta_numerator // delta_denominator

    return order.auction_start_price - price_delta

def get_auction_price_for_oracle_offset_auction(order: Order, slot: int, oracle_price: int) -> int:
    """
    Calculate the auction price for an oracle offset auction.
    
    Args:
    order (Order): The order object.
    slot (int): The current slot.
    oracle_price (int): The current oracle price.
    
    Returns:
    int: The calculated auction price.
    """
    slots_elapsed = slot - order.slot
    delta_denominator = order.auction_duration
    delta_numerator = min(slots_elapsed, delta_denominator)

    if delta_denominator == 0:
        return oracle_price + order.auction_end_price

    direction_multiplier: Literal[1, -1] = 1 if is_variant(order.direction, "Long") else -1

    price_offset_delta = direction_multiplier * (
        order.auction_start_price
        - order.auction_end_price
    ) * delta_numerator // delta_denominator

    price_offset = order.auction_start_price - price_offset_delta

    return oracle_price + price_offset

def is_fallback_available_liquidity_source(order: Order, min_auction_duration: int, slot: int) -> bool:
    """
    Check if fallback liquidity source is available.
    
    Args:
    order (Order): The order object.
    min_auction_duration (int): The minimum auction duration.
    slot (int): The current slot.
    
    Returns:
    bool: True if fallback liquidity source is available, False otherwise.
    """
    if min_auction_duration == 0:
        return True
    return slot - order.slot > min_auction_duration

def derive_oracle_auction_params(
    direction: PositionDirection,
    oracle_price: int,
    auction_start_price: int,
    auction_end_price: int,
    limit_price: int,
) -> Tuple[int, int, int]:
    """
    Derive oracle auction parameters.
    
    Args:
    direction (PositionDirection): The position direction.


oracle_price (int): The current oracle price.
    auction_start_price (int): The auction start price.
    auction_end_price (int): The auction end price.
    limit_price (int): The limit price.
    
    Returns:
    Tuple[int, int, int]: A tuple containing the adjusted auction start price, 
                          auction end price, and oracle price offset.
    """
    oracle_price_offset = limit_price - oracle_price

    if oracle_price_offset == 0:
        if is_variant(direction, "Long"):
            oracle_price_offset = (auction_end_price - oracle_price) + 1
        else:
            oracle_price_offset = (auction_end_price - oracle_price) - 1

    auction_start_price -= oracle_price
    auction_end_price -= oracle_price

    return (auction_start_price, auction_end_price, oracle_price_offset)
    
