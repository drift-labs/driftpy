import math
from xmlrpc.client import boolean
from driftpy.math.amm import (
    calculate_price,
    calculate_amm_reserves_after_swap,
    calculate_spread_reserves,
    calculate_peg_multiplier,
    get_swap_direction,
)
from driftpy.math.market import (
    calculate_ask_price,
    calculate_bid_price,
    calculate_mark_price,
    calculate_bid_ask_price,
    calculate_candidate_amm,
)

from driftpy.constants.numeric_constants import (
    PRICE_PRECISION as PRICE_PRECISION,
    PEG_PRECISION,
    AMM_TO_QUOTE_PRECISION_RATIO,
)

from driftpy.types import PositionDirection, PerpMarket, AMM
from driftpy.sdk_types import AssetType


def calculate_trade_acquired_amounts(
    direction: PositionDirection,
    amount: int,
    market: PerpMarket,
    input_asset_type=AssetType,
    use_spread: boolean = True,
):
    if amount == 0:
        return [0, 0]

    amm = None
    if use_spread:
        base_asset_reserve, quote_asset_reserve = calculate_spread_reserves(
            market.amm, direction
        )
        amm = AMM(
            base_asset_reserve,
            quote_asset_reserve,
            sqrt_k=market.amm.sqrt_k,
            peg_multiplier=market.amm.peg_multiplier,
        )
    else:
        amm = market.amm

    [
        new_quote_asset_reserve,
        new_base_asset_reserve,
    ] = calculate_amm_reserves_after_swap(
        amm,
        input_asset_type,
        amount,
        get_swap_direction(input_asset_type, direction),
    )

    acquired_base = amm.base_asset_reserve - new_base_asset_reserve
    acquired_quote = amm.quote_asset_reserve - new_quote_asset_reserve

    # if input_asset_type == AssetType.BASE and direction == PositionDirection.LONG:
    #     acquired_quote -= 1  # round up

    return [acquired_base, acquired_quote]


""""""


def calculate_trade_slippage(
    direction: PositionDirection,
    amount: int,
    market: PerpMarket,
    input_asset_type: AssetType,
    use_spread: boolean = True,
):
    old_price = None
    if use_spread:
        if direction == PositionDirection.LONG:
            old_price = calculate_ask_price(market)
        else:
            old_price = calculate_bid_price(market)
    else:
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

    amm = None
    if use_spread:
        base_asset_reserve, quote_asset_reserve = calculate_spread_reserves(
            market.amm, direction
        )
        amm = AMM(
            base_asset_reserve,
            quote_asset_reserve,
            sqrt_k=market.amm.sqrt_k,
            peg_multiplier=market.amm.peg_multiplier,
        )
    else:
        amm = market.amm

    new_price = calculate_price(
        amm.base_asset_reserve - acquired_base,
        amm.quote_asset_reserve - acquired_quote,
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
    market: PerpMarket,
    target_price: float,
    output_asset_type: AssetType,
    use_spread: boolean = True,
    oracle_price=None,
):
    mark_price_before = calculate_mark_price(market, oracle_price) * PRICE_PRECISION
    bid_price_before, ask_price_before = calculate_bid_ask_price(market, oracle_price)
    bid_price_before *= PRICE_PRECISION
    ask_price_before *= PRICE_PRECISION

    # bid_price_before = calculate_bid_price(market, oracle_price) * PRICE_PRECISION
    # ask_price_before = calculate_ask_price(market, oracle_price) * PRICE_PRECISION

    if target_price > mark_price_before:
        #     price_gap = target_price - mark_price_before
        #     target_price = mark_price_before + price_gap
        direction = PositionDirection.LONG
    else:
        direction = PositionDirection.SHORT
    #     price_gap = mark_price_before - target_price
    #     target_price = mark_price_before - price_gap

    candidate_amm = calculate_candidate_amm(market, oracle_price)
    peg = candidate_amm.peg_multiplier

    # print(candidate_amm.base_asset_reserve, candidate_amm.quote_asset_reserve)
    if use_spread:
        # print(direction)
        (
            base_asset_reserve_before,
            quote_asset_reserve_before,
        ) = calculate_spread_reserves(
            candidate_amm, direction, oracle_price=oracle_price
        )
        # print(base_asset_reserve_before, quote_asset_reserve_before)
        # print(market.amm.strategies)
    else:
        base_asset_reserve_before = market.amm.base_asset_reserve
        quote_asset_reserve_before = market.amm.quote_asset_reserve

    # print(direction, mark_price_before/1e10, peg/1e3)
    invariant = (float(market.amm.sqrt_k)) ** 2
    k = invariant * PRICE_PRECISION
    bias_modifier = 0

    if (
        use_spread
        and target_price < ask_price_before
        and target_price > bid_price_before
    ):
        if mark_price_before > target_price:
            direction = PositionDirection.SHORT
        else:
            direction = PositionDirection.LONG
        tradeSize = 0
        print("canot trade:", bid_price_before, target_price, ask_price_before)
        return [direction, tradeSize, target_price, target_price]
    elif mark_price_before > target_price:
        base_asset_reserve_after = (
            math.sqrt((k / target_price) * (float(peg) / PEG_PRECISION) - bias_modifier)
            - 1
        )
        quote_asset_reserve_after = (k / PRICE_PRECISION) / base_asset_reserve_after

        direction = PositionDirection.SHORT
        trade_size = (
            (quote_asset_reserve_before - quote_asset_reserve_after)
            * (float(peg) / PEG_PRECISION)
        ) / AMM_TO_QUOTE_PRECISION_RATIO
        base_size = base_asset_reserve_after - base_asset_reserve_before
        # print('ARB SHORT', peg/PEG_PRECISION, base_size/1e13, trade_size/1e6)

    elif mark_price_before < target_price:
        base_asset_reserve_after = (
            math.sqrt((k / target_price) * (float(peg) / PEG_PRECISION) + bias_modifier)
            + 1
        )
        quote_asset_reserve_after = (k / PRICE_PRECISION) / base_asset_reserve_after

        direction = PositionDirection.LONG
        print("long", quote_asset_reserve_after, quote_asset_reserve_before, peg)
        trade_size = (
            (quote_asset_reserve_after - quote_asset_reserve_before)
            * ((peg) / PEG_PRECISION)
        ) / AMM_TO_QUOTE_PRECISION_RATIO
        base_size = base_asset_reserve_before - base_asset_reserve_after
        # print('ARB LONG', peg/PEG_PRECISION, base_size/1e13, trade_size/1e6)
    else:
        # no trade, market is at target
        print("NO TRADE")
        direction = PositionDirection.LONG
        trade_size = 0
        return [direction, trade_size, target_price, target_price]

    if base_size != 0:
        entry_price = trade_size * AMM_TO_QUOTE_PRECISION_RATIO / base_size

        # print(quote_asset_reserve_before, base_asset_reserve_before, peg)

        # print('CUR PRICE:', quote_asset_reserve_before/base_asset_reserve_before*market.amm.peg_multiplier/1e3,
        #  '->', quote_asset_reserve_before/base_asset_reserve_before*peg/1e3)

        # print(peg, market.amm.peg_multiplier, direction)
        if direction == PositionDirection.SHORT:
            #     print(base_asset_reserve_before)
            #     print((
            #     math.sqrt((k / target_price) * (float(peg) / PEG_PRECISION) - bias_modifier) - 1
            # ) - base_asset_reserve_before)
            #     print((
            #         math.sqrt((k / (entry_price*1e10)) * (float(peg) / PEG_PRECISION) - bias_modifier) - 1
            #     ) - base_asset_reserve_before)
            if not (entry_price * PRICE_PRECISION >= target_price):
                # problem!
                print(
                    "ERR:",
                    direction,
                    mark_price_before / PRICE_PRECISION,
                    bid_price_before / PRICE_PRECISION,
                    target_price / PRICE_PRECISION,
                    entry_price,
                )
                tradeSize = 0
                # assert(False)

                return [direction, tradeSize, target_price, target_price]
        else:
            #     print(base_asset_reserve_before)
            #     print(market.amm.sqrt_k)
            #     print((
            #     math.sqrt((k / target_price) * (float(peg) / PEG_PRECISION) - bias_modifier) - 1
            # ) - base_asset_reserve_before)
            #     print((
            #         math.sqrt((k / (entry_price*1e10)) * (float(peg) / PEG_PRECISION) - bias_modifier) - 1
            #     ) - base_asset_reserve_before)
            if not (entry_price * PRICE_PRECISION <= target_price):
                # problem!
                print(
                    "ERR:",
                    direction,
                    mark_price_before / PRICE_PRECISION,
                    ask_price_before / PRICE_PRECISION,
                    target_price / PRICE_PRECISION,
                    entry_price,
                )
                tradeSize = 0
                # assert(False)
                return [direction, tradeSize, target_price, target_price]
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
