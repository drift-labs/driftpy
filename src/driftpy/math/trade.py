import math
from driftpy.math.amm import calculate_price, calculate_amm_reserves_after_swap
from driftpy.math.market import calculate_mark_price

from driftpy.constants import (
    MARK_PRICE_PRECISION,
    PEG_PRECISION,
    FUNDING_PRECISION,
    # AMM_RESERVE_PRECISION,
    AMM_TO_QUOTE_PRECISION_RATIO,
)


""""""


def calculate_trade_acquired_amounts(
    direction, amount, market, input_asset_type="quote"
):
    if amount == 0:
        return [0, 0]

    [
        new_quote_asset_reserve,
        new_base_asset_reserve,
    ] = calculate_amm_reserves_after_swap(
        market.amm, input_asset_type, amount, direction
    )

    acquired_base = (
        market.amm.base_asset_reserve / MARK_PRICE_PRECISION - new_base_asset_reserve
    )
    acquired_quote = (
        market.amm.quote_asset_reserve / MARK_PRICE_PRECISION - new_quote_asset_reserve
    )

    return [acquired_base, acquired_quote]


""""""


def calculate_trade_slippage(direction, amount, market, input_asset_type="quote"):

    old_price = calculate_mark_price(market)
    if amount == 0:
        return [0, 0, old_price, old_price]

    [acquired_base, acquired_quote] = calculate_trade_acquired_amounts(
        direction, amount, market, input_asset_type
    )

    entry_price = (
        calculate_price(
            acquired_base,
            acquired_quote,
            market.amm.peg_multiplier * (-1) / MARK_PRICE_PRECISION,
        )
        * MARK_PRICE_PRECISION
    )

    new_price = (
        calculate_price(
            market.amm.base_asset_reserve / MARK_PRICE_PRECISION - acquired_base,
            market.amm.quote_asset_reserve / MARK_PRICE_PRECISION - acquired_quote,
            market.amm.peg_multiplier / MARK_PRICE_PRECISION,
        )
        * MARK_PRICE_PRECISION
    )

    if direction == "SHORT":
        assert new_price < old_price
    else:
        assert old_price < new_price

    pct_max_slippage = abs((new_price - old_price) / old_price)
    pct_avg_slippage = abs((entry_price - old_price) / old_price)

    return [pct_avg_slippage, pct_max_slippage, entry_price, new_price]


def calculate_target_price_trade(
    market, target_price: float, output_asset_type="quote"
):

    mark_price_before = calculate_mark_price(market)

    if target_price > mark_price_before:
        price_gap = target_price - mark_price_before
        target_price = mark_price_before + price_gap
    else:
        price_gap = mark_price_before - target_price
        target_price = mark_price_before - price_gap

    base_asset_reserve_before = market.amm.base_asset_reserve / MARK_PRICE_PRECISION
    quote_asset_reserve_before = market.amm.quote_asset_reserve / MARK_PRICE_PRECISION
    peg = market.amm.peg_multiplier / MARK_PRICE_PRECISION
    invariant = (market.amm.sqrt_k / MARK_PRICE_PRECISION) ** 2
    k = invariant * MARK_PRICE_PRECISION
    bias_modifier = 1

    if mark_price_before > target_price:
        base_asset_reserve_after = (
            math.sqrt((k / target_price) * (peg / PEG_PRECISION) - bias_modifier) - 1
        )
        quote_asset_reserve_after = (
            k / MARK_PRICE_PRECISION
        ) / base_asset_reserve_after

        direction = "SHORT"
        trade_size = (
            (quote_asset_reserve_before - quote_asset_reserve_after)
            * (peg / PEG_PRECISION)
        ) / AMM_TO_QUOTE_PRECISION_RATIO
        base_size = base_asset_reserve_after - base_asset_reserve_before

    elif mark_price_before < target_price:
        base_asset_reserve_after = (
            math.sqrt((k / target_price) * (peg / PEG_PRECISION) + bias_modifier) + 1
        )
        quote_asset_reserve_after = (
            k / MARK_PRICE_PRECISION
        ) / base_asset_reserve_after

        direction = "LONG"
        trade_size = (
            (quote_asset_reserve_after - quote_asset_reserve_before)
            * (peg / PEG_PRECISION)
        ) / AMM_TO_QUOTE_PRECISION_RATIO
        base_size = base_asset_reserve_before - base_asset_reserve_after

    else:
        # no trade, market is at target
        direction = "LONG"
        trade_size = 0
        return [direction, trade_size, target_price, target_price]

    entry_price = (
        trade_size
        * AMM_TO_QUOTE_PRECISION_RATIO
        * MARK_PRICE_PRECISION
        / abs(base_size)
    )

    if output_asset_type == "quote":
        return [
            direction,
            trade_size * MARK_PRICE_PRECISION * FUNDING_PRECISION,
            entry_price,
            target_price,
        ]
    else:
        return [direction, base_size / PEG_PRECISION, entry_price, target_price]
