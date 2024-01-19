from typing import Optional
from driftpy.math.amm import (
    calculate_max_base_asset_amount_to_trade,
    calculate_updated_amm,
)
from driftpy.math.auction import (
    get_auction_price,
    is_auction_complete,
    is_fallback_available_liquidity_source,
)
from driftpy.types import (
    AMM,
    OraclePriceData,
    Order,
    PerpMarketAccount,
    PositionDirection,
    is_one_of_variant,
    is_variant,
)


def get_limit_price(
    order: Order,
    oracle_price_data: OraclePriceData,
    slot: int,
    fallback_price: Optional[int] = None,
) -> int:
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
    return not is_auction_complete(order, slot) and (
        order.auction_start_price != 0 or order.auction_end_price != 0
    )


def standardize_price(price: int, tick_size: int, direction: PositionDirection) -> int:
    if price == 0:
        print("price is zero")
        return price

    remainder = price % tick_size
    if remainder == 0:
        return price

    if is_variant(direction, "Long"):
        return price - remainder
    else:
        return price + tick_size - remainder


def standardize_base_asset_amount(base_asset_amount: int, step_size: int) -> int:
    remainder = base_asset_amount % step_size
    return base_asset_amount - remainder


def is_market_order(order: Order) -> bool:
    return is_one_of_variant(order.order_type, ["Market", "TriggerMarket", "Oracle"])


def is_limit_order(order: Order) -> bool:
    return is_one_of_variant(order.order_type, ["Limit", "TriggerLimit"])


def must_be_triggered(order: Order) -> bool:
    return is_one_of_variant(order.order_type, ["TriggerMarket", "TriggerLimit"])


def is_triggered(order: Order) -> bool:
    return is_one_of_variant(
        order.trigger_condition, ["TriggeredAbove", "TriggeredBelow"]
    )


def is_resting_limit_order(order: Order, slot: int) -> bool:
    if not is_limit_order(order):
        return False

    if is_variant(order.order_type, "TriggerLimit"):
        if is_variant(order.direction, "Long") and order.trigger_price < order.price:
            return False
        elif is_variant(order.direction, "Short") and order.trigger_price > order.price:
            return False

        return is_auction_complete(order, slot)

    return order.post_only or is_auction_complete(order, slot)


def is_order_expired(order: Order, ts: int, enforce_buffer: bool = False) -> bool:
    if (
        must_be_triggered(order)
        or not is_variant(order.status, "Open")
        or order.max_ts == 0
    ):
        return False

    if enforce_buffer and is_limit_order(order):
        max_ts = order.max_ts + 15
    else:
        max_ts = order.max_ts

    return ts > max_ts


def is_taking_order(order: Order, slot: int) -> bool:
    return is_market_order(order) or not is_resting_limit_order(order, slot)


def is_fillable_by_vamm(
    order: Order,
    market: PerpMarketAccount,
    oracle_price_data: OraclePriceData,
    slot: int,
    ts: int,
    min_auction_duration: int,
) -> bool:
    rhs = is_fallback_available_liquidity_source(order, min_auction_duration, slot)
    lhs = calculate_base_asset_amount_for_amm_to_fulfill(
        order, market, oracle_price_data, slot
    ) > (market.amm.min_order_size)

    return (lhs and rhs) or is_order_expired(order, ts)


def calculate_base_asset_amount_for_amm_to_fulfill(
    order: Order,
    market: PerpMarketAccount,
    oracle_price_data: OraclePriceData,
    slot: int,
) -> int:
    if must_be_triggered(order) and not is_triggered(order):
        return 0

    limit_price = get_limit_price(order, oracle_price_data, slot)

    updated_amm = calculate_updated_amm(market.amm, oracle_price_data)
    if limit_price:
        base_asset_amount = calculate_base_asset_amount_to_fill_up_to_limit_price(
            order, updated_amm, limit_price, oracle_price_data
        )
    else:
        base_asset_amount = order.base_asset_amount - order.base_asset_amount_filled

    max_base_asset_amount = calculate_max_base_asset_amount_fillable(
        updated_amm, order.direction
    )

    return min(max_base_asset_amount, base_asset_amount)


def calculate_base_asset_amount_to_fill_up_to_limit_price(
    order: Order, amm: AMM, limit_price: int, oracle_price_data: OraclePriceData
) -> int:
    adjusted_limit_price = (
        limit_price - amm.order_tick_size
        if is_variant(order.direction, "Long")
        else limit_price + amm.order_tick_size
    )

    (max_amount_to_trade, direction) = calculate_max_base_asset_amount_to_trade(
        amm, adjusted_limit_price, order.direction, oracle_price_data
    )

    base_asset_amount = standardize_base_asset_amount(
        max_amount_to_trade, amm.order_step_size
    )

    if not same_direction(direction, order.direction):
        return 0

    base_asset_amount_unfilled = (
        order.base_asset_amount - order.base_asset_amount_filled
    )

    return min(base_asset_amount, base_asset_amount_unfilled)


def calculate_max_base_asset_amount_fillable(
    amm: AMM, order_direction: PositionDirection
) -> int:
    max_fill_size = amm.base_asset_reserve // amm.max_fill_reserve_fraction

    if is_variant(order_direction, "Long"):
        max_base_asset_amount_on_side = max(
            0, amm.base_asset_reserve - amm.min_base_asset_reserve
        )
    else:
        max_base_asset_amount_on_side = max(
            0, amm.max_base_asset_reserve - amm.base_asset_reserve
        )

    return standardize_base_asset_amount(
        min(max_fill_size, max_base_asset_amount_on_side), amm.order_step_size
    )


def same_direction(lhs: PositionDirection, rhs: PositionDirection) -> bool:
    return (is_variant(lhs, "Long") and is_variant(rhs, "Long")) or (
        is_variant(lhs, "Short") and is_variant(rhs, "Short")
    )
