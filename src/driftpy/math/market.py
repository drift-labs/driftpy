from driftpy.math.amm import (
    calculate_price,
    calculate_spread_reserves,
    calculate_peg_multiplier,
    calculate_terminal_price,
    calculate_budgeted_repeg,
)
from driftpy.types import PositionDirection
import copy
from solana.publickey import PublicKey
import numpy as np
# from driftpy.math.positions import calculate_base_asset_value, calculate_position_pnl
from driftpy.constants.numeric_constants import (
    AMM_RESERVE_PRECISION,
    AMM_TIMES_PEG_TO_QUOTE_PRECISION_RATIO,
    PEG_PRECISION,
    QUOTE_PRECISION,
)


def calculate_freepeg_cost(market, target_price, bonus=0):
    def calculate_budgeted_k(market, cost):
        if cost == 0:
            return 1

        C = cost
        x = market.amm.base_asset_reserve / AMM_RESERVE_PRECISION
        y = market.amm.quote_asset_reserve / AMM_RESERVE_PRECISION
        d = market.base_asset_amount / AMM_RESERVE_PRECISION
        Q = market.amm.peg_multiplier / PEG_PRECISION

        numer = y * d * d * Q - C * d * (x + d)
        denom = C * x * (x + d) + y * d * d * Q
        # print('budget k params', C, x, y, d, Q)
        print(y * d * d * Q, C * d * (x + d), C * x * (x + d))
        print(numer, denom)
        p = numer / denom
        return p

    def calculate_repeg_cost(market, new_peg):
        k = int(market.amm.sqrt_k) ** 2
        new_quote_reserves = k / (
            market.amm.base_asset_reserve + market.base_asset_amount
        )
        delta_quote_reserves = new_quote_reserves - market.amm.quote_asset_reserve

        cost2 = (
            delta_quote_reserves * (market.amm.peg_multiplier - new_peg)
        ) / AMM_TIMES_PEG_TO_QUOTE_PRECISION_RATIO

        mark_delta = (
            (market.amm.quote_asset_reserve / market.amm.base_asset_reserve)
            * (new_peg - market.amm.peg_multiplier)
            / PEG_PRECISION
        )

        return cost2 / 1e6, mark_delta

    def calculate_k_cost(market, p):
        x = market.amm.base_asset_reserve / AMM_RESERVE_PRECISION
        y = market.amm.quote_asset_reserve / AMM_RESERVE_PRECISION
        d = market.base_asset_amount / AMM_RESERVE_PRECISION
        Q = market.amm.peg_multiplier / PEG_PRECISION

        cost = -((1 / (x + d) - p / (x * p + d)) * y * d * Q)
        return cost

    pk = 1.0
    new_peg = (
        target_price * market.amm.base_asset_reserve / market.amm.quote_asset_reserve
    )
    optimal_peg_cost, _ = calculate_repeg_cost(market, int(new_peg * PEG_PRECISION))
    if bonus < optimal_peg_cost:
        print("MUST LOWER K FOR FREEPEG")
        deficit = bonus - optimal_peg_cost
        pk = max(0.985, calculate_budgeted_k(market, -deficit))
        deficit_madeup = -calculate_k_cost(market, pk)
        print(deficit_madeup, pk)
        assert deficit_madeup > 0
        freepeg_cost = bonus + deficit_madeup
        new_peg = calculate_budgeted_repeg(market.amm, freepeg_cost, target_price)
        return freepeg_cost, pk, pk, int(new_peg * PEG_PRECISION)

    return optimal_peg_cost, pk, pk, int(new_peg * PEG_PRECISION)


def calculate_candidate_amm(market, oracle_price=None):
    prepeg = "PrePeg" in market.amm.strategies
    prefreepeg = "PreFreePeg" in market.amm.strategies

    base_scale = 1
    quote_scale = 1

    budget_cost = None  # max(0, (market.amm.total_fee_minus_distributions/1e6)/2)
    fee_pool = (market.amm.total_fee_minus_distributions / QUOTE_PRECISION) - (
        market.amm.total_fee / QUOTE_PRECISION
    ) / 2
    budget_cost = max(0, fee_pool)
    # print('BUDGET_COST', budget_cost)
    if prepeg:
        peg = calculate_peg_multiplier(
            market.amm, oracle_price, budget_cost=budget_cost
        )
    elif prefreepeg:
        freepeg_cost, base_scale, quote_scale, peg = calculate_freepeg_cost(
            market, oracle_price, bonus=budget_cost
        )
        # print(freepeg_cost, 'is cost to freepeg')
    else:
        peg = market.amm.peg_multiplier

    candidate_amm = copy.deepcopy(market.amm)
    candidate_amm.base_asset_reserve *= float(base_scale)
    candidate_amm.quote_asset_reserve *= float(quote_scale)
    candidate_amm.peg_multiplier = peg
    if base_scale != 1 or quote_scale != 1:
        candidate_amm.sqrt_k = np.sqrt(
            candidate_amm.base_asset_reserve * candidate_amm.quote_asset_reserve
        )

    candidate_amm.terminal_quote_asset_reserve = (candidate_amm.sqrt_k ** 2) / (
        candidate_amm.base_asset_reserve + candidate_amm.base_asset_amount_with_amm
    )
    return candidate_amm


def calculate_long_short_reserves_and_peg(market, oracle_price=None):
    candidate_amm = calculate_candidate_amm(market, oracle_price)

    base_asset_reserves_short, quote_asset_reserves_short = calculate_spread_reserves(
        candidate_amm, PositionDirection.SHORT, oracle_price=oracle_price
    )

    base_asset_reserves_long, quote_asset_reserves_long = calculate_spread_reserves(
        candidate_amm, PositionDirection.LONG, oracle_price=oracle_price
    )

    return [
        base_asset_reserves_long,
        quote_asset_reserves_long,
        base_asset_reserves_short,
        quote_asset_reserves_short,
        candidate_amm.peg_multiplier,
    ]


def calculate_mark_price(market, oracle_price=None):
    if oracle_price is not None:
        candidate_amm = calculate_candidate_amm(market, oracle_price)
    else:
        candidate_amm = market.amm

    return calculate_price(
        candidate_amm.base_asset_reserve,
        candidate_amm.quote_asset_reserve,
        candidate_amm.peg_multiplier,
    )


def calculate_bid_ask_price(market, oracle_price=None):
    [
        base_asset_reserves_long,
        quote_asset_reserves_long,
        base_asset_reserves_short,
        quote_asset_reserves_short,
        peg_multiplier,
    ] = calculate_long_short_reserves_and_peg(market, oracle_price)

    bid_price = calculate_price(
        base_asset_reserves_short, quote_asset_reserves_short, peg_multiplier
    )

    ask_price = calculate_price(
        base_asset_reserves_long, quote_asset_reserves_long, peg_multiplier
    )

    return bid_price, ask_price


def calculate_bid_price(market, oracle_price=None):
    candidate_amm = calculate_candidate_amm(market, oracle_price)

    base_asset_reserves_short, quote_asset_reserves_short = calculate_spread_reserves(
        candidate_amm, PositionDirection.SHORT, oracle_price=oracle_price
    )

    return calculate_price(
        base_asset_reserves_short,
        quote_asset_reserves_short,
        candidate_amm.peg_multiplier,
    )


def calculate_ask_price(market, oracle_price=None):
    candidate_amm = calculate_candidate_amm(market, oracle_price)

    base_asset_reserves_long, quote_asset_reserves_long = calculate_spread_reserves(
        candidate_amm, PositionDirection.LONG, oracle_price=oracle_price
    )

    return calculate_price(
        base_asset_reserves_long,
        quote_asset_reserves_long,
        candidate_amm.peg_multiplier,
    )
