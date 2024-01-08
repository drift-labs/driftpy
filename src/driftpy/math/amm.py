from copy import deepcopy
import math
import time
from typing import Optional
from driftpy.constants.numeric_constants import (
    AMM_RESERVE_PRECISION,
    AMM_TO_QUOTE_PRECISION_RATIO,
    BID_ASK_SPREAD_PRECISION,
    DEFAULT_REVENUE_SINCE_LAST_FUNDING_SPREAD_RETREAT,
    PERCENTAGE_PRECISION,
    PRICE_DIV_PEG,
    PEG_PRECISION,
    AMM_TIMES_PEG_TO_QUOTE_PRECISION_RATIO,
    PRICE_PRECISION,
    QUOTE_PRECISION,
)
from driftpy.math.oracles import calculate_live_oracle_std
from driftpy.math.repeg import (
    calculate_adjust_k_cost,
    calculate_budgeted_peg,
    calculate_optimal_peg_and_budget,
    calculate_repeg_cost,
)
from driftpy.math.utils import clamp_num
from driftpy.types import (
    OraclePriceData,
    PositionDirection,
    SwapDirection,
    AMM,
    AssetType,
    is_variant,
)


def calculate_vol_spread_bn(
    last_oracle_conf_pct: int,
    reserve_price: int,
    mark_std: int,
    oracle_std: int,
    long_intensity: int,
    short_intensity: int,
    volume_24h: int,
):
    market_avg_std_pct = (
        ((mark_std + oracle_std) * PERCENTAGE_PRECISION) // reserve_price
    ) // 2
    vol_spread = max(last_oracle_conf_pct, market_avg_std_pct // 2)

    clamp_min = PERCENTAGE_PRECISION // 100
    clamp_max = (PERCENTAGE_PRECISION * 16) // 10

    long_vol_spread_factor = clamp_num(
        (long_intensity * PERCENTAGE_PRECISION) // max(1, volume_24h),
        clamp_min,
        clamp_max,
    )
    short_vol_spread_factor = clamp_num(
        (short_intensity * PERCENTAGE_PRECISION) // max(1, volume_24h),
        clamp_min,
        clamp_max,
    )

    conf_component = last_oracle_conf_pct

    if last_oracle_conf_pct <= PRICE_PRECISION // 400:
        conf_component = last_oracle_conf_pct // 10

    long_vol_spread = max(
        conf_component, (vol_spread * long_vol_spread_factor) // PERCENTAGE_PRECISION
    )
    short_vol_spread = max(
        conf_component, (vol_spread * short_vol_spread_factor) // PERCENTAGE_PRECISION
    )

    return long_vol_spread, short_vol_spread


def calculate_effective_leverage(
    base_spread: int,
    quote_asset_reserve: int,
    terminal_quote_asset_reserve: int,
    peg_multiplier: int,
    net_base_asset_amount: int,
    reserve_price: int,
    total_fee_minus_distributions: int,
) -> int:
    # vAMM skew
    net_base_asset_value = (
        (quote_asset_reserve - terminal_quote_asset_reserve) * peg_multiplier
    ) // AMM_TIMES_PEG_TO_QUOTE_PRECISION_RATIO

    local_base_asset_value = (net_base_asset_amount * reserve_price) // (
        AMM_TO_QUOTE_PRECISION_RATIO * PRICE_PRECISION
    )

    effective_gap = max(0, local_base_asset_value - net_base_asset_value)

    effective_leverage = (
        effective_gap / (max(0, total_fee_minus_distributions) + 1)
        + 1 / QUOTE_PRECISION
    )

    return effective_leverage


def calculate_inventory_scale(
    base_asset_amount_with_amm: int,
    base_asset_reserve: int,
    min_base_asset_reserve: int,
    max_base_asset_reserve: int,
    directional_spread: float,
    max_spread: float,
) -> float:
    if base_asset_amount_with_amm == 0:
        return 1

    max_bid_ask_inventory_skew_factor = BID_ASK_SPREAD_PRECISION * 10

    open_bids, open_asks = calculate_market_open_bid_ask(
        base_asset_reserve, min_base_asset_reserve, max_base_asset_reserve
    )

    min_side_liquidity = min(abs(open_bids), abs(open_asks))

    inventory_scale_bn = min(
        abs(
            (base_asset_amount_with_amm * PERCENTAGE_PRECISION)
            // max(min_side_liquidity, 1)
        ),
        PERCENTAGE_PRECISION,
    )

    inventory_scale_max_bn = max(
        max_bid_ask_inventory_skew_factor,
        (max_spread * BID_ASK_SPREAD_PRECISION) // max(directional_spread, 1),
    )

    inventory_scale_capped = (
        min(
            inventory_scale_max_bn,
            BID_ASK_SPREAD_PRECISION
            + ((inventory_scale_max_bn * inventory_scale_bn) // PERCENTAGE_PRECISION),
        )
        / BID_ASK_SPREAD_PRECISION
    )

    return inventory_scale_capped


def calculate_spread_bn(
    base_spread: int,
    last_oracle_reserve_price_spread_pct: int,
    last_oracle_conf_pct: int,
    max_spread: int,
    quote_asset_reserve: int,
    terminal_quote_asset_reserve: int,
    peg_multiplier: int,
    base_asset_amount_with_amm: int,
    reserve_price: int,
    total_fee_minus_distributions: int,
    net_revenue_since_last_funding: int,
    base_asset_reserve: int,
    min_base_asset_reserve: int,
    max_base_asset_reserve: int,
    mark_std: int,
    oracle_std: int,
    long_intensity: int,
    short_intensity: int,
    volume24H: int,
    return_terms: bool = False,
):
    assert isinstance(base_spread, int)
    assert isinstance(max_spread, int)

    spread_terms = {
        "long_vol_spread": 0,
        "short_vol_spread": 0,
        "long_spread_w_ps": 0,
        "short_spread_w_ps": 0,
        "max_target_spread": 0,
        "inventory_spread_scale": 0,
        "long_spread_w_inv_scale": 0,
        "short_spread_w_inv_scale": 0,
        "effective_leverage": 0,
        "effective_leverage_capped": 0,
        "long_spread_w_el": 0,
        "short_spread_w_el": 0,
        "revenue_retreat_amount": 0,
        "half_revenue_retreat_amount": 0,
        "long_spread_w_rev_retreat": 0,
        "short_spread_w_rev_retreat": 0,
        "total_spread": 0,
        "long_spread": 0,
        "short_spread": 0,
    }

    long_vol_spread, short_vol_spread = calculate_vol_spread_bn(
        last_oracle_conf_pct,
        reserve_price,
        mark_std,
        oracle_std,
        long_intensity,
        short_intensity,
        volume24H,
    )

    spread_terms["long_vol_spread"] = long_vol_spread
    spread_terms["short_vol_spread"] = short_vol_spread

    long_spread = max(base_spread / 2, long_vol_spread)
    short_spread = max(base_spread / 2, short_vol_spread)

    if last_oracle_reserve_price_spread_pct > 0:
        short_spread = max(
            short_spread,
            abs(last_oracle_reserve_price_spread_pct) + short_vol_spread,
        )
    elif last_oracle_reserve_price_spread_pct < 0:
        long_spread = max(
            long_spread,
            abs(last_oracle_reserve_price_spread_pct) + long_vol_spread,
        )

    spread_terms["long_spread_w_ps"] = long_spread
    spread_terms["short_spread_w_ps"] = short_spread

    max_target_spread = float(
        math.floor(max(max_spread, abs(last_oracle_reserve_price_spread_pct)))
    )

    inventory_spread_scale = calculate_inventory_scale(
        base_asset_amount_with_amm,
        base_asset_reserve,
        min_base_asset_reserve,
        max_base_asset_reserve,
        long_spread if base_asset_amount_with_amm > 0 else short_spread,
        max_target_spread,
    )

    if base_asset_amount_with_amm > 0:
        long_spread *= inventory_spread_scale
    elif base_asset_amount_with_amm < 0:
        short_spread *= inventory_spread_scale

    spread_terms["max_target_spread"] = max_target_spread
    spread_terms["inventory_spread_scale"] = inventory_spread_scale
    spread_terms["long_spread_w_inv_scale"] = long_spread
    spread_terms["short_spread_w_inv_scale"] = short_spread

    MAX_SPREAD_SCALE = 10
    if total_fee_minus_distributions > 0:
        effective_leverage = calculate_effective_leverage(
            base_spread,
            quote_asset_reserve,
            terminal_quote_asset_reserve,
            peg_multiplier,
            base_asset_amount_with_amm,
            reserve_price,
            total_fee_minus_distributions,
        )
        spread_terms["effective_leverage"] = effective_leverage

        spread_scale = min(MAX_SPREAD_SCALE, 1 + effective_leverage)

        spread_terms["effective_leverage_capped"] = spread_scale

        if base_asset_amount_with_amm > 0:
            long_spread *= spread_scale
            long_spread = math.floor(long_spread)
        else:
            short_spread *= spread_scale
            short_spread = math.floor(short_spread)
    else:
        long_spread *= MAX_SPREAD_SCALE
        short_spread *= MAX_SPREAD_SCALE

    spread_terms["long_spread_w_el"] = long_spread
    spread_terms["short_spread_w_el"] = short_spread

    if (
        net_revenue_since_last_funding
        < DEFAULT_REVENUE_SINCE_LAST_FUNDING_SPREAD_RETREAT
    ):
        max_retreat = max_target_spread // 10
        revenue_retreat_amount = max_retreat

        if (
            net_revenue_since_last_funding
            >= DEFAULT_REVENUE_SINCE_LAST_FUNDING_SPREAD_RETREAT * 1000
        ):
            revenue_retreat_amount = min(
                max_retreat,
                math.floor(
                    (base_spread * abs(net_revenue_since_last_funding))
                    / abs(DEFAULT_REVENUE_SINCE_LAST_FUNDING_SPREAD_RETREAT)
                ),
            )

        half_revenue_retreat_amount = math.floor(revenue_retreat_amount / 2)

        spread_terms["revenue_retreat_amount"] = revenue_retreat_amount
        spread_terms["half_revenue_retreat_amount"] = half_revenue_retreat_amount

        if base_asset_amount_with_amm > 0:
            long_spread += revenue_retreat_amount
            short_spread += half_revenue_retreat_amount
        elif base_asset_amount_with_amm < 0:
            long_spread += half_revenue_retreat_amount
            short_spread += revenue_retreat_amount
        else:
            long_spread += half_revenue_retreat_amount
            short_spread += half_revenue_retreat_amount

    spread_terms["long_spread_w_rev_retreat"] = long_spread
    spread_terms["short_spread_w_rev_retreat"] = short_spread

    total_spread = long_spread + short_spread
    if total_spread > max_target_spread:
        if long_spread > short_spread:
            long_spread = math.ceil((long_spread * max_target_spread) / total_spread)
            short_spread = math.floor(max_target_spread - long_spread)
        else:
            short_spread = math.ceil((short_spread * max_target_spread) / total_spread)
            long_spread = math.floor(max_target_spread - short_spread)

    spread_terms["total_spread"] = total_spread
    spread_terms["long_spread"] = long_spread
    spread_terms["short_spread"] = short_spread

    if return_terms:
        return spread_terms
    return long_spread, short_spread


def calculate_spread(
    amm: AMM, oracle_price_data: OraclePriceData, now: Optional[int] = None
) -> tuple[float, float]:
    if amm.base_spread == 0 or amm.curve_update_intensity == 0:
        return amm.base_spread // 2, amm.base_spread // 2

    reserve_price = calculate_price(
        amm.base_asset_reserve, amm.quote_asset_reserve, amm.peg_multiplier
    )

    target_price = oracle_price_data.price or reserve_price
    conf_interval = oracle_price_data.confidence or 0

    target_mark_spread_pct = (
        (reserve_price - target_price) * BID_ASK_SPREAD_PRECISION
    ) // reserve_price
    conf_interval_pct = (conf_interval * BID_ASK_SPREAD_PRECISION) // reserve_price

    now = now or int(time.time())
    live_oracle_std = calculate_live_oracle_std(amm, oracle_price_data, now)

    spreads = calculate_spread_bn(
        amm.base_spread,
        target_mark_spread_pct,
        conf_interval_pct,
        amm.max_spread,
        amm.quote_asset_reserve,
        amm.terminal_quote_asset_reserve,
        amm.peg_multiplier,
        amm.base_asset_amount_with_amm,
        reserve_price,
        amm.total_fee_minus_distributions,
        amm.net_revenue_since_last_funding,
        amm.base_asset_reserve,
        amm.min_base_asset_reserve,
        amm.max_base_asset_reserve,
        amm.mark_std,
        live_oracle_std,
        amm.long_intensity_volume,
        amm.short_intensity_volume,
        amm.volume24h,
    )

    long_spread = spreads[0]
    short_spread = spreads[1]

    return long_spread, short_spread


def calculate_peg_from_target_price(
    target_price: int, base_asset_reserves: int, quote_asset_reserves: int
) -> int:
    peg_maybe = (
        ((target_price * base_asset_reserves) // quote_asset_reserves)
        + (PRICE_DIV_PEG // 2)
    ) // PRICE_DIV_PEG
    return max(peg_maybe, 1)


def calculate_mark_price_amm(amm: AMM):
    return calculate_price(
        amm.base_asset_reserve,
        amm.quote_asset_reserve,
        amm.peg_multiplier,
    )


def calculate_mark_price_amm(amm, oracle_price=None):
    dynamic_peg = "PrePeg" in amm.strategies

    if dynamic_peg:
        peg = calculate_peg_multiplier(amm, oracle_price)
    else:
        peg = amm.peg_multiplier

    return calculate_price(
        amm.base_asset_reserve,
        amm.quote_asset_reserve,
        peg,
    )


def calculate_bid_price_amm(amm: AMM, oracle_price=None):
    base_asset_reserves, quote_asset_reserves = calculate_spread_reserves(
        amm, PositionDirection.Short, oracle_price=oracle_price
    )
    return calculate_price(
        base_asset_reserves, quote_asset_reserves, amm.peg_multiplier
    )


def calculate_ask_price_amm(amm: AMM, oracle_price=None):
    base_asset_reserves, quote_asset_reserves = calculate_spread_reserves(
        amm, PositionDirection.Long, oracle_price=oracle_price
    )
    return calculate_price(
        base_asset_reserves, quote_asset_reserves, amm.peg_multiplier
    )


def calculate_bid_ask_price(
    amm: AMM, oracle_price_data: OraclePriceData, with_update: bool = False
) -> tuple[int, int]:
    if with_update:
        new_amm = calculate_updated_amm(amm, oracle_price_data)
    else:
        new_amm = amm

    bid_reserves, ask_reserves = calculate_spread_reserves_dlob(
        new_amm, oracle_price_data
    )

    bid_price = calculate_price(
        bid_reserves[0], bid_reserves[1], new_amm.peg_multiplier
    )

    ask_price = calculate_price(
        ask_reserves[0], ask_reserves[1], new_amm.peg_multiplier
    )

    return bid_price, ask_price


def calculate_price(
    base_asset_amount: int, quote_asset_amount: int, peg_multiplier: int
):
    if abs(base_asset_amount) == 0:
        return 0
    else:
        return (
            quote_asset_amount
            * PRICE_PRECISION
            * peg_multiplier
            // PEG_PRECISION
            // base_asset_amount
        )


def calculate_terminal_price(market):
    swap_direction = (
        SwapDirection.Add() if market.base_asset_amount > 0 else SwapDirection.Remove()
    )

    new_quote_asset_amount, new_base_asset_amount = calculate_swap_output(
        abs(market.base_asset_amount),
        market.amm.base_asset_reserve,
        swap_direction,
        market.amm.sqrt_k,
    )

    terminal_price = calculate_price(
        new_base_asset_amount,
        new_quote_asset_amount,
        market.amm.peg_multiplier,
    )

    return terminal_price


def calculate_swap_output(
    swap_amount: int,
    input_asset_reserve: int,
    swap_direction: SwapDirection,
    invariant: int,
):
    if is_variant(swap_direction, "Add"):
        new_input_asset_reserve = input_asset_reserve + swap_amount
    else:
        new_input_asset_reserve = input_asset_reserve - swap_amount

    new_output_asset_reserve = invariant // new_input_asset_reserve

    return (new_input_asset_reserve, new_output_asset_reserve)


def calculate_amm_reserves_after_swap(
    amm,
    input_asset_type: AssetType,
    swap_amount,
    swap_direction: SwapDirection,
):
    assert swap_amount >= 0, "swap_amount must be non-neg"

    if is_variant(input_asset_type, "QUOTE"):
        swap_amount = (
            swap_amount * AMM_TIMES_PEG_TO_QUOTE_PRECISION_RATIO
        ) // amm.peg_multiplier

        (new_quote_asset_reserve, new_base_asset_reserve) = calculate_swap_output(
            amm.quote_asset_reserve,
            swap_amount,
            swap_direction,
            amm.sqrt_k * amm.sqrt_k,
        )
    else:
        (new_base_asset_reserve, new_quote_asset_reserve) = calculate_swap_output(
            amm.base_asset_reserve, swap_amount, swap_direction, amm.sqrt_k * amm.sqrt_k
        )

    return (new_quote_asset_reserve, new_base_asset_reserve)


def get_swap_direction(
    input_asset_type: AssetType, position_direction: PositionDirection
) -> SwapDirection:
    assert input_asset_type in [
        AssetType.BASE(),
        AssetType.QUOTE(),
    ], "invalid input_asset_type: " + str(input_asset_type)
    assert position_direction in [
        PositionDirection.Long(),
        PositionDirection.Short(),
    ], "invalid position_direction: " + str(position_direction)
    if (
        position_direction == PositionDirection.Long()
        and input_asset_type == AssetType.BASE()
    ):
        return SwapDirection.Remove()

    if (
        position_direction == PositionDirection.Short()
        and input_asset_type == AssetType.QUOTE()
    ):
        return SwapDirection.Remove()

    return SwapDirection.Add()


def calculate_budgeted_repeg(amm, cost, target_px=None, pay_only=False):
    if target_px is None:
        target_px = amm.last_oracle_price  # / 1e10
        assert amm.last_oracle_price != 0

    C = cost
    x = amm.base_asset_reserve / AMM_RESERVE_PRECISION
    y = amm.quote_asset_reserve / AMM_RESERVE_PRECISION
    d = amm.base_asset_amount_with_amm / AMM_RESERVE_PRECISION
    Q = amm.peg_multiplier / PEG_PRECISION
    k = (amm.sqrt_k / AMM_RESERVE_PRECISION) ** 2

    dqar = y - (k / (x + d))

    cur_px = y / x * Q
    target_peg = target_px * x / y

    peg_change_direction = target_peg - Q

    use_target_peg = (dqar < 0 and peg_change_direction > 0) or (
        dqar > 0 and peg_change_direction < 0
    )

    if dqar != 0 and not use_target_peg:
        new_peg = Q + (C / dqar)
    else:
        new_peg = target_peg

    if cur_px > target_px and new_peg < target_peg:
        new_peg = target_peg
    if cur_px < target_px and new_peg > target_peg:
        new_peg = target_peg

    if pay_only:
        if new_peg < Q and d > 0:
            new_peg = Q
        if new_peg > Q and d < 0:
            new_peg = Q

    return new_peg


def calculate_peg_multiplier(
    amm, oracle_price=None, now=None, delay=None, budget_cost=None
):
    # todo: make amm have all the vars needed
    if "PrePeg" in amm.strategies:
        if oracle_price is None:
            oracle_price = amm.last_oracle_price
            if delay is None:
                if now is not None:
                    delay = now - amm.last_oracle_price_twap_ts
                else:
                    delay = 100
            # delay_discount = 1/(delay*delay/2)
            # last_mark = calculate_mark_price_amm(market.amm)
            # target_px = last_mark + ((oracle_price-last_mark)*delay_discount)
            target_px = oracle_price
        else:
            target_px = oracle_price

        if budget_cost is None:
            fee_pool = (amm.total_fee_minus_distributions / QUOTE_PRECISION) - (
                amm.total_fee / QUOTE_PRECISION
            ) / 2
            budget_cost = max(0, fee_pool)

        new_peg = int(
            calculate_budgeted_repeg(amm, budget_cost, target_px=target_px)
            * PEG_PRECISION
        )
        return new_peg
    elif "PreFreePeg" in amm.strategies:
        target_px = oracle_price

        if budget_cost is None:
            fee_pool = (amm.total_fee_minus_distributions / QUOTE_PRECISION) - (
                amm.total_fee / QUOTE_PRECISION
            ) / 2
            budget_cost = max(0, fee_pool)

        new_peg = int(
            calculate_budgeted_repeg(amm, budget_cost, target_px=target_px)
            * PEG_PRECISION
        )
        return new_peg
    else:
        return amm.peg_multiplier


def calculate_spread_reserves(
    amm, position_direction: PositionDirection, oracle_price=None
):
    BID_ASK_SPREAD_PRECISION = 1_000_000  # this is 100% (thus 1_000 = .1%)
    mark_price = calculate_mark_price_amm(amm, oracle_price=oracle_price)
    spread = amm.base_spread

    if "OracleRetreat" in amm.strategies:
        if oracle_price is None:
            oracle_price = amm.last_oracle_price
        pct_delta = float(oracle_price - mark_price) / mark_price
        if (pct_delta > 0 and position_direction == PositionDirection.Long) or (
            pct_delta < 0 and position_direction == PositionDirection.Short
        ):
            oracle_spread = abs(pct_delta) * QUOTE_PRECISION * 2
            if oracle_spread > spread:
                spread = oracle_spread * 2
        else:
            # no retreat
            pass

    if "VolatilityScale" in amm.strategies:
        spread *= min(2, max(1, amm.mark_std))

    if "InventorySkew" in amm.strategies:
        max_scale = 5  # if 'OracleRetreat' not in amm.strategies else 20

        effective_position = (
            amm.base_asset_amount_with_amm
        )  # (amm.sqrt_k - amm.base_asset_reserve)

        net_cost_basis = (
            amm.quote_asset_amount_long - (amm.quote_asset_amount_short)
        ) / QUOTE_PRECISION
        net_base_asset_value = (
            (amm.quote_asset_reserve - amm.terminal_quote_asset_reserve)
            / AMM_RESERVE_PRECISION
            * amm.peg_multiplier
            / PEG_PRECISION
        )
        local_base_asset_value = mark_price * (
            effective_position / AMM_RESERVE_PRECISION
        )

        local_pnl = local_base_asset_value - net_cost_basis
        net_pnl = net_base_asset_value - net_cost_basis
        if amm.total_fee_minus_distributions > 0:
            effective_leverage = (local_pnl - net_pnl) / (
                amm.total_fee_minus_distributions / QUOTE_PRECISION
            )
            print("effective_leverage:", effective_leverage)
            if position_direction == PositionDirection.Long:
                spread *= min(max_scale, max(1, (1 + effective_leverage)))
            else:
                spread *= min(max_scale, max(1, (1 - effective_leverage)))
        else:
            spread *= max_scale

    amm.last_spread = spread

    quote_asset_reserve_delta = 0
    if spread > 0:
        quote_asset_reserve_delta = amm.quote_asset_reserve / (
            BID_ASK_SPREAD_PRECISION / (spread / 4)
        )

    if position_direction == PositionDirection.Long:
        quote_asset_reserve = amm.quote_asset_reserve + quote_asset_reserve_delta
    else:
        quote_asset_reserve = amm.quote_asset_reserve - quote_asset_reserve_delta

    base_asset_reserve = (amm.sqrt_k * amm.sqrt_k) / quote_asset_reserve
    return base_asset_reserve, quote_asset_reserve


def calculate_spread_reserves_dlob(
    amm: AMM, oracle_price_data: OraclePriceData, now=None
):
    """
    This is meant to replace `get_spread_reserves` eventually to match the TS SDK
    """

    def calculate_spread_reserve(spread: int, direction: PositionDirection, amm: AMM):
        if spread == 0:
            return amm.base_asset_reserve, amm.quote_asset_reserve

        spread_fraction = int(max(spread / 2, 1))
        quote_asset_reserve_delta = amm.quote_asset_reserve // (
            BID_ASK_SPREAD_PRECISION / spread_fraction
        )

        if is_variant(direction, "Long"):
            quote_asset_reserve = amm.quote_asset_reserve + quote_asset_reserve_delta
        else:
            quote_asset_reserve = amm.quote_asset_reserve - quote_asset_reserve_delta

        base_asset_reserve = (amm.sqrt_k * amm.sqrt_k) // quote_asset_reserve

        return base_asset_reserve, quote_asset_reserve

    long_spread, short_spread = calculate_spread(amm, oracle_price_data, now)

    ask_reserves = calculate_spread_reserve(long_spread, PositionDirection.Long(), amm)
    bid_reserves = calculate_spread_reserve(
        short_spread, PositionDirection.Short(), amm
    )

    return bid_reserves, ask_reserves


def calculate_quote_asset_amount_swapped(
    quote_asset_reserves: int, peg_multiplier: int, swap_direction: SwapDirection
) -> int:
    if is_variant(swap_direction, "Remove"):
        quote_asset_reserves += 1

    quote_asset_amount = (
        quote_asset_reserves * peg_multiplier // AMM_TIMES_PEG_TO_QUOTE_PRECISION_RATIO
    )

    if is_variant(swap_direction, "Remove"):
        quote_asset_amount += 1

    return quote_asset_amount


def calculate_market_open_bid_ask(
    base_asset_reserve: int,
    min_base_asset_reserve: int,
    max_base_asset_reserve: int,
    step_size: Optional[int] = None,
):
    if min_base_asset_reserve < base_asset_reserve:
        open_asks = (base_asset_reserve - min_base_asset_reserve) * -1
        if step_size and abs(open_asks) // 2 < step_size:
            open_asks = 0
    else:
        open_asks = 0

    if max_base_asset_reserve > base_asset_reserve:
        open_bids = max_base_asset_reserve - base_asset_reserve
        if step_size and open_bids // 2 < step_size:
            open_bids = 0
    else:
        open_bids = 0

    return open_bids, open_asks


def calculate_updated_amm(amm: AMM, oracle_price_data: OraclePriceData) -> AMM:
    if amm.curve_update_intensity == 0 or oracle_price_data is None:
        return amm

    new_amm = deepcopy(amm)
    (prepeg_cost, p_k_numer, p_k_denom, new_peg) = calculate_new_amm(
        amm, oracle_price_data
    )

    new_amm.base_asset_reserve = (new_amm.base_asset_reserve * p_k_numer) // p_k_denom
    new_amm.sqrt_k = (new_amm.sqrt_k * p_k_numer) // p_k_denom
    invariant = new_amm.sqrt_k * new_amm.sqrt_k
    new_amm.quote_asset_reserve = invariant // new_amm.base_asset_reserve
    new_amm.peg_multiplier = new_peg

    direction_to_close = (
        PositionDirection.Short()
        if amm.base_asset_amount_with_amm > 0
        else PositionDirection.Long()
    )

    (
        new_quote_asset_reserve,
        _new_base_asset_reserve,
    ) = calculate_amm_reserves_after_swap(
        new_amm,
        AssetType.BASE(),
        abs(amm.base_asset_amount_with_amm),
        get_swap_direction(AssetType.BASE(), direction_to_close),
    )

    new_amm.terminal_quote_asset_reserve = new_quote_asset_reserve
    new_amm.total_fee_minus_distributions = (
        new_amm.total_fee_minus_distributions - prepeg_cost
    )
    new_amm.net_revenue_since_last_funding = (
        new_amm.net_revenue_since_last_funding - prepeg_cost
    )

    return new_amm


def calculate_new_amm(amm: AMM, oracle_price_data: OraclePriceData):
    p_k_numer = 1
    p_k_denom = 1

    (
        target_price,
        _new_peg,
        budget,
        _check_lower_bound,
    ) = calculate_optimal_peg_and_budget(amm, oracle_price_data)
    pre_peg_cost = calculate_repeg_cost(amm, _new_peg)
    new_peg = _new_peg

    if pre_peg_cost >= budget and pre_peg_cost > 0:
        p_k_numer = 999
        p_k_denom = 1_000

        deficit_makeup = calculate_adjust_k_cost(amm, p_k_numer, p_k_denom)

        assert deficit_makeup <= 0, "deficit should be lte 0"

        pre_peg_cost = budget + abs(deficit_makeup)

        new_amm = deepcopy(amm)

        new_amm.base_asset_reserve = (
            new_amm.base_asset_reserve * p_k_numer
        ) // p_k_denom
        new_amm.sqrt_k = (new_amm.sqrt_k * p_k_numer) // p_k_denom

        invariant = new_amm.sqrt_k * new_amm.sqrt_k
        new_amm.quote_asset_reserve = invariant // new_amm.base_asset_reserve

        direction_to_close = (
            PositionDirection.Short()
            if amm.base_asset_amount_with_amm > 0
            else PositionDirection.Long()
        )

        (
            new_quote_asset_reserve,
            _new_base_asset_reserve,
        ) = calculate_amm_reserves_after_swap(
            new_amm,
            AssetType.BASE(),
            abs(amm.base_asset_amount_with_amm),
            get_swap_direction(AssetType.BASE(), direction_to_close),
        )

        new_amm.terminal_quote_asset_reserve = new_quote_asset_reserve
        new_peg = calculate_budgeted_peg(new_amm, pre_peg_cost, target_price)
        pre_peg_cost = calculate_repeg_cost(new_amm, new_peg)

    return (pre_peg_cost, p_k_numer, p_k_denom, new_peg)


def calculate_updated_amm_spread_reserves(
    amm: AMM, direction: PositionDirection, oracle_price_data: OraclePriceData
):
    new_amm = calculate_updated_amm(amm, oracle_price_data)
    (long_reserves, short_reserves) = calculate_spread_reserves_dlob(
        new_amm, oracle_price_data
    )

    dir_reserves = long_reserves if is_variant(direction, "Long") else short_reserves

    return dir_reserves[0], dir_reserves[1], new_amm.sqrt_k, new_amm.peg_multiplier


# async def main():
#     # Try out  the functions here

#     # Initiate drift client
#     drift_acct = await DriftClient.create(program)
#     drift_user_acct = await drift_acct.get_user_account()

#     # Get the total value of your collateral
#     balance = drift_user_acct.collateral / 1e6
#     print(f"Total Collateral: {balance}")

#     asset = "SOL"  # Select which asset you want to use here

#     drift_assets = [
#         "SOL",
#         "BTC",
#         "ETH",
#         "LUNA",
#         "AVAX",
#         "BNB",
#         "MATIC",
#         "ATOM",
#         "DOT",
#         "ALGO",
#     ]
#     idx = drift_assets.index(asset)

#     markets = await drift_acct.get_markets_account()
#     market = markets.markets[idx]

#     markets_summary = calculate_market_summary(markets)

#     # Get the predicted funding rates of each market
#     print(calculate_predicted_funding(markets, markets_summary))

#     # Liquidity required to move AMM price of SOL to 95
#     print(calculate_target_price_trade(market, 95, output_asset_type="quote"))

#     # Slippage of a $5000 long trade
#     print(calculate_trade_slippage("LONG", 5000, market, input_asset_type="quote"))


# asyncio.run(main())
