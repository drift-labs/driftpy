from typing import Tuple

from driftpy.types import (
    Order,
    OrderBitFlag,
    PositionDirection,
    is_one_of_variant,
    is_variant,
)


def is_auction_complete(order: Order, slot: int) -> bool:
    if order.auction_duration == 0:
        return True

    return slot - order.slot > order.auction_duration


def get_auction_price(order: Order, slot: int, oracle_price: int) -> int:
    if is_one_of_variant(order.order_type, ["Market", "TriggerLimit"]) or (
        is_variant(order.order_type, "TriggerMarket")
        and (order.bit_flags & OrderBitFlag.OracleTriggerMarket) == 0
    ):
        return get_auction_price_for_fixed_auction(order, slot)
    elif is_variant(order.order_type, "Limit"):
        if order.oracle_price_offset != 0:
            return get_auction_price_for_oracle_offset_auction(
                order, slot, oracle_price
            )
        else:
            return get_auction_price_for_fixed_auction(order, slot)
    elif is_variant(order.order_type, "Oracle") or (
        is_variant(order.order_type, "TriggerMarket")
        and (order.bit_flags & OrderBitFlag.OracleTriggerMarket) != 0
    ):
        return get_auction_price_for_oracle_offset_auction(order, slot, oracle_price)
    else:
        raise ValueError(f"Can't get auction price for order type {order.order_type}")


def get_auction_price_for_fixed_auction(order: Order, slot: int) -> int:
    slots_elapsed = slot - order.slot

    delta_denominator = order.auction_duration
    delta_numerator = min(slots_elapsed, delta_denominator)

    if delta_denominator == 0:
        return order.auction_end_price

    if is_variant(order.direction, "Long"):
        price_delta = (
            order.auction_end_price
            - order.auction_start_price * delta_numerator // delta_denominator
        )
    else:
        price_delta = (
            order.auction_start_price
            - order.auction_end_price * delta_numerator // delta_denominator
        )

    if is_variant(order.direction, "Long"):
        price = order.auction_start_price + price_delta
    else:
        price = order.auction_start_price - price_delta

    return price


def get_auction_price_for_oracle_offset_auction(
    order: Order, slot: int, oracle_price: int
) -> int:
    slots_elapsed = slot - order.slot

    delta_denominator = order.auction_duration
    delta_numerator = min(slots_elapsed, delta_denominator)

    if delta_denominator == 0:
        return oracle_price + order.auction_end_price

    if is_variant(order.direction, "Long"):
        price_offset_delta = (
            order.auction_end_price
            - order.auction_start_price * delta_numerator // delta_denominator
        )
    else:
        price_offset_delta = (
            order.auction_start_price
            - order.auction_end_price * delta_numerator // delta_denominator
        )

    if is_variant(order.direction, "Long"):
        price_offset = order.auction_start_price + price_offset_delta
    else:
        price_offset = order.auction_start_price - price_offset_delta

    return oracle_price + price_offset


def is_fallback_available_liquidity_source(
    order: Order, min_auction_duration: int, slot: int
) -> bool:
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
    oracle_price_offset = limit_price - oracle_price

    if oracle_price_offset == 0:
        if is_variant(direction, "Long"):
            oracle_price_offset = (auction_end_price - oracle_price) + 1
        else:
            oracle_price_offset = (auction_end_price - oracle_price) - 1

    auction_start_price = auction_start_price - oracle_price
    auction_end_price = auction_end_price - oracle_price
    oracle_price_offset = oracle_price_offset

    return (auction_start_price, auction_end_price, oracle_price_offset)
