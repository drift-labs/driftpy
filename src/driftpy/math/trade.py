import math
from driftpy.math.amm import (
    calculate_price,
    calculate_amm_reserves_after_swap,
    get_swap_direction,
)
from driftpy.math.market import calculate_mark_price

from driftpy.constants.numeric_constants import (
    MARK_PRICE_PRECISION,
    PEG_PRECISION,
    AMM_TO_QUOTE_PRECISION_RATIO,
)

# from driftpy.src.driftpy.constants.numeric_constants import AMM_RESERVE_PRECISION

from driftpy.types import PositionDirection, Market, AssetType


""""""


def calculate_trade_acquired_amounts(
    direction: PositionDirection,
    amount: int,
    market: Market,
    input_asset_type=AssetType,
):
    if amount == 0:
        return [0, 0]

    [
        new_quote_asset_reserve,
        new_base_asset_reserve,
    ] = calculate_amm_reserves_after_swap(
        market.amm,
        input_asset_type,
        amount,
        get_swap_direction(input_asset_type, direction),
    )

    acquired_base = market.amm.base_asset_reserve - new_base_asset_reserve
    acquired_quote = market.amm.quote_asset_reserve - new_quote_asset_reserve

    if input_asset_type == AssetType.BASE and direction == PositionDirection.LONG:
        acquired_quote -= 1  # round up

    return [acquired_base, acquired_quote]


""""""


def calculate_trade_slippage(
    direction: PositionDirection,
    amount: int,
    market: Market,
    input_asset_type: AssetType,
):

    old_price = calculate_mark_price(market)
    if amount == 0:
        return [0, 0, old_price, old_price]

    [acquired_base, acquired_quote] = calculate_trade_acquired_amounts(
        direction, amount, market, input_asset_type
    )
    entry_price = calculate_price(
        abs(acquired_base),
        abs(acquired_quote),
        market.amm.peg_multiplier,
    )

    new_price = calculate_price(
        market.amm.base_asset_reserve - acquired_base,
        market.amm.quote_asset_reserve - acquired_quote,
        market.amm.peg_multiplier,
    )

    # print(old_price, '->', new_price)
    if direction == PositionDirection.SHORT:
        assert new_price < old_price
    else:
        # print(new_price, old_price)
        assert new_price > old_price

    pct_max_slippage = abs((new_price - old_price) / old_price)
    pct_avg_slippage = abs((entry_price - old_price) / old_price)
    return [pct_avg_slippage, pct_max_slippage, entry_price, new_price]


def calculate_target_price_trade(
    market: Market, target_price: float, output_asset_type: AssetType
):

    mark_price_before = calculate_mark_price(market) * MARK_PRICE_PRECISION

    # if target_price > mark_price_before:
    #     price_gap = target_price - mark_price_before
    #     target_price = mark_price_before + price_gap
    # else:
    #     price_gap = mark_price_before - target_price
    #     target_price = mark_price_before - price_gap

    base_asset_reserve_before = market.amm.base_asset_reserve
    quote_asset_reserve_before = market.amm.quote_asset_reserve
    peg = market.amm.peg_multiplier
    invariant = (float(market.amm.sqrt_k)) ** 2
    k = invariant * MARK_PRICE_PRECISION
    bias_modifier = 0

    if mark_price_before > target_price:
        base_asset_reserve_after = (
            math.sqrt((k / target_price) * (peg / PEG_PRECISION) - bias_modifier) - 1
        )
        quote_asset_reserve_after = (
            k / MARK_PRICE_PRECISION
        ) / base_asset_reserve_after

        direction = PositionDirection.SHORT
        trade_size = (
            (quote_asset_reserve_before - quote_asset_reserve_after)
            * (peg / float(PEG_PRECISION))
        ) / AMM_TO_QUOTE_PRECISION_RATIO
        base_size = base_asset_reserve_after - base_asset_reserve_before

    elif mark_price_before < target_price:
        base_asset_reserve_after = (
            math.sqrt((k / target_price) * (peg / PEG_PRECISION) + bias_modifier) + 1
        )
        quote_asset_reserve_after = (
            k / MARK_PRICE_PRECISION
        ) / base_asset_reserve_after

        direction = PositionDirection.LONG
        trade_size = (
            (quote_asset_reserve_after - quote_asset_reserve_before)
            * (peg / PEG_PRECISION)
        ) / AMM_TO_QUOTE_PRECISION_RATIO
        base_size = base_asset_reserve_before - base_asset_reserve_after

    else:
        # no trade, market is at target
        direction = PositionDirection.LONG
        trade_size = 0
        return [direction, trade_size, target_price, target_price]

    if base_size != 0:
        entry_price = trade_size * AMM_TO_QUOTE_PRECISION_RATIO / abs(base_size)
    else:
        entry_price = 0

    if output_asset_type == AssetType.QUOTE:
        return [
            direction,
            trade_size,
            entry_price,
            target_price,
        ]
    else:
        return [direction, base_size, entry_price, target_price]
