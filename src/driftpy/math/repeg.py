import math
from driftpy.constants.numeric_constants import *
from driftpy.types import OraclePriceData, AMM
from driftpy.constants.numeric_constants import (
    PEG_PRECISION,
)


def calculate_optimal_peg_and_budget(
    amm: AMM, oracle_price_data: OraclePriceData
) -> tuple[int, int, int, bool]:
    from driftpy.math.amm import calculate_peg_from_target_price, calculate_price

    reserve_price_before = calculate_price(
        amm.base_asset_reserve, amm.quote_asset_reserve, amm.peg_multiplier
    )

    target_price = oracle_price_data.price

    new_peg = calculate_peg_from_target_price(
        target_price, amm.base_asset_reserve, amm.quote_asset_reserve
    )

    pre_peg_cost = calculate_repeg_cost(amm, new_peg)

    total_fee_lb = amm.total_exchange_fee // 2
    budget = max(0, amm.total_fee_minus_distributions - total_fee_lb)

    check_lower_bound = True
    if budget < pre_peg_cost:
        half_max_price_spread = (
            (amm.max_spread // 2) * target_price
        ) // BID_ASK_SPREAD_PRECISION

        target_price_gap = reserve_price_before - target_price

        if abs(target_price_gap) > half_max_price_spread:
            mark_adj = abs(target_price_gap) - half_max_price_spread

            if target_price_gap < 0:
                new_target_price = reserve_price_before + mark_adj
            else:
                new_target_price = reserve_price_before - mark_adj

            new_optimal_peg = calculate_peg_from_target_price(
                new_target_price, amm.base_asset_reserve, amm.quote_asset_reserve
            )

            new_budget = calculate_repeg_cost(amm, new_optimal_peg)
            check_lower_bound = False

            return (new_target_price, new_optimal_peg, new_budget, check_lower_bound)
        elif amm.total_fee_minus_distributions < amm.total_exchange_fee // 2:
            check_lower_bound = False

    return (target_price, new_peg, budget, check_lower_bound)


def calculate_repeg_cost(amm: AMM, new_peg: int) -> int:
    dqar = amm.quote_asset_reserve - amm.terminal_quote_asset_reserve
    cost = (
        (dqar * (new_peg - amm.peg_multiplier)) / AMM_TO_QUOTE_PRECISION_RATIO
    ) / PEG_PRECISION
    return math.floor(cost)


def calculate_k_cost(market, p):
    x = market.amm.base_asset_reserve / AMM_RESERVE_PRECISION
    y = market.amm.quote_asset_reserve / AMM_RESERVE_PRECISION
    d = market.base_asset_amount / AMM_RESERVE_PRECISION
    Q = market.amm.peg_multiplier / PEG_PRECISION

    cost = -((1 / (x + d) - p / (x * p + d)) * y * d * Q)
    return cost


def calculate_budgeted_k(market, cost):
    C = cost
    x = market.amm.base_asset_reserve / AMM_RESERVE_PRECISION
    y = market.amm.quote_asset_reserve / AMM_RESERVE_PRECISION
    d = market.base_asset_amount / AMM_RESERVE_PRECISION
    Q = market.amm.peg_multiplier / PEG_PRECISION

    numer = y * d * d * Q - C * d * (x + d)
    denom = C * x * (x + d) + y * d * d * Q
    # print(C, x, y, d, Q)
    # print(numer, denom)
    p = numer / denom
    return p


def calculate_budgeted_peg(amm: AMM, budget: int, target_price: int) -> int:
    per_peg_cost = (amm.quote_asset_reserve - amm.terminal_quote_asset_reserve) // (
        AMM_RESERVE_PRECISION // PRICE_PRECISION
    )

    if per_peg_cost > 0:
        per_peg_cost += 1
    elif per_peg_cost < 0:
        per_peg_cost -= 1

    target_peg = (
        target_price
        * amm.base_asset_reserve
        // amm.quote_asset_reserve
        // PRICE_DIV_PEG
    )
    peg_change_direction = target_peg - amm.peg_multiplier

    use_target_peg = (per_peg_cost < 0 and peg_change_direction > 0) or (
        per_peg_cost > 0 and peg_change_direction < 0
    )

    if per_peg_cost == 0 or use_target_peg:
        return target_peg

    budget_delta_peg = budget * PEG_PRECISION // per_peg_cost
    new_peg = max(1, amm.peg_multiplier + budget_delta_peg)

    return new_peg


def calculate_adjust_k_cost(amm: AMM, numerator: int, denominator: int) -> int:
    x = amm.base_asset_reserve
    y = amm.quote_asset_reserve

    d = amm.base_asset_amount_with_amm
    Q = amm.peg_multiplier

    quote_scale = y * d * Q // AMM_RESERVE_PRECISION

    p = numerator * PRICE_PRECISION // denominator

    cost = (
        (quote_scale * PERCENTAGE_PRECISION * PERCENTAGE_PRECISION // (x + d))
        - (
            quote_scale
            * p
            * PERCENTAGE_PRECISION
            * PERCENTAGE_PRECISION
            // PRICE_PRECISION
            // (x * p // PRICE_PRECISION + d)
        )
        // PERCENTAGE_PRECISION
        // PERCENTAGE_PRECISION
        // AMM_TO_QUOTE_PRECISION_RATIO
        // PEG_PRECISION
    )

    return cost * -1
