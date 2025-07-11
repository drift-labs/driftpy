import math
import time
from copy import deepcopy
from dataclasses import fields
from solders.pubkey import Pubkey
from typing import Optional, Tuple

from driftpy.constants.numeric_constants import (
    AMM_TIMES_PEG_TO_QUOTE_PRECISION_RATIO,
    AMM_TO_QUOTE_PRECISION_RATIO,
    BID_ASK_SPREAD_PRECISION,
    DEFAULT_REVENUE_SINCE_LAST_FUNDING_SPREAD_RETREAT,
    FUNDING_RATE_BUFFER,
    PEG_PRECISION,
    PERCENTAGE_PRECISION,
    PRICE_DIV_PEG,
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
from driftpy.math.utils import clamp_num, sig_num
from driftpy.types import (
    AMM,
    AssetType,
    OraclePriceData,
    PositionDirection,
    SwapDirection,
    is_variant,
)


def deepcopy_amm(amm: AMM) -> AMM:
    field_values = {}
    field_names = {field.name for field in fields(AMM)}
    for field in amm.__dataclass_fields__.values():
        value = getattr(amm, field.name)
        if isinstance(value, Pubkey):
            field_values[field.name] = value
        elif field.name in field_names:
            field_values[field.name] = deepcopy(value)
    copied = AMM(**field_values)
    return copied


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
    ) // 4
    vol_spread = max(last_oracle_conf_pct, market_avg_std_pct // 2)

    clamp_min = PERCENTAGE_PRECISION // 100
    clamp_max = PERCENTAGE_PRECISION

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
        conf_component = last_oracle_conf_pct // 20

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


def calculate_reference_price_offset(
    reserve_price: int,
    last_24h_avg_funding_rate: int,
    liquidity_fraction: int,
    oracle_twap_fast: int,
    mark_twap_fast: int,
    oracle_twap_slow: int,
    mark_twap_slow: int,
    max_offset_pct: float,
):
    if last_24h_avg_funding_rate == 0:
        return 0

    max_offset_in_price = (max_offset_pct * reserve_price) // PERCENTAGE_PRECISION

    # calc quote denom market premium
    mark_premium_minute = clamp_num(
        mark_twap_fast - oracle_twap_fast, max_offset_in_price * -1, max_offset_in_price
    )

    mark_premium_hour = clamp_num(
        mark_twap_slow - oracle_twap_slow, max_offset_in_price * -1, max_offset_in_price
    )

    # convert funding to quote denom premium
    mark_premium_day = clamp_num(
        (last_24h_avg_funding_rate // FUNDING_RATE_BUFFER) * 24,
        max_offset_in_price * -1,
        max_offset_in_price,
    )

    mark_premium_avg = (mark_premium_minute + mark_premium_hour + mark_premium_day) // 3

    mark_premium_avg_pct = (mark_premium_avg * PRICE_PRECISION) // reserve_price

    inventory_pct = clamp_num(
        liquidity_fraction * max_offset_pct // PERCENTAGE_PRECISION,
        max_offset_in_price * -1,
        max_offset_in_price,
    )

    # only apply when inv is consistent with recent and 24h market premim
    offset_pct = mark_premium_avg_pct + inventory_pct

    if not sig_num(inventory_pct) == sig_num(mark_premium_avg_pct):
        offset_pct = 0

    clamped_offset_pct = clamp_num(offset_pct, max_offset_pct * -1, max_offset_pct)

    return clamped_offset_pct


def calculate_inventory_liquidity_ratio(
    base_asset_amount_with_amm: int,
    base_asset_reserve: int,
    min_base_asset_reserve: int,
    max_base_asset_reserve: int,
) -> int:
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

    return inventory_scale_bn


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

    inventory_scale_bn = calculate_inventory_liquidity_ratio(
        base_asset_amount_with_amm,
        base_asset_reserve,
        min_base_asset_reserve,
        max_base_asset_reserve,
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
    amm_inventory_spread_adjustment: int = 0,
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
        "long_spread_w_offset_shrink": 0,
        "short_spread_w_offset_shrink": 0,
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

    max_spread_baseline = min(
        max(
            abs(last_oracle_reserve_price_spread_pct),
            last_oracle_conf_pct * 2,
            max(mark_std, oracle_std) * PERCENTAGE_PRECISION // reserve_price,
        ),
        BID_ASK_SPREAD_PRECISION,
    )

    max_target_spread = float(math.floor(max(max_spread, max_spread_baseline)))

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

    if amm_inventory_spread_adjustment < 0:
        adjustment = abs(amm_inventory_spread_adjustment)

        shrunk_long = max(1, long_spread - math.floor((long_spread * adjustment) / 100))
        shrunk_short = max(
            1, short_spread - math.floor((short_spread * adjustment) / 100)
        )

        long_spread = max(long_vol_spread, shrunk_long)
        short_spread = max(short_vol_spread, shrunk_short)
    elif amm_inventory_spread_adjustment > 0:
        adjustment = amm_inventory_spread_adjustment

        grown_long = max(1, long_spread + math.ceil((long_spread * adjustment) / 100))
        grown_short = max(
            1, short_spread + math.ceil((short_spread * adjustment) / 100)
        )

        long_spread = max(long_vol_spread, grown_long)
        short_spread = max(short_vol_spread, grown_short)

    spread_terms["long_spread_w_offset_shrink"] = long_spread
    spread_terms["short_spread_w_offset_shrink"] = short_spread

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
    amm: AMM,
    oracle_price_data: OraclePriceData,
    now: Optional[int] = None,
    reserve_price: Optional[int] = None,
) -> tuple[float, float]:
    if amm.base_spread == 0 or amm.curve_update_intensity == 0:
        return amm.base_spread // 2, amm.base_spread // 2

    if not reserve_price:
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
        amm.amm_inventory_spread_adjustment,
    )

    long_spread = spreads[0]
    short_spread = spreads[1]

    amm_spread_adjustment = amm.amm_spread_adjustment
    if amm_spread_adjustment > 0:
        long_spread = max(long_spread + (long_spread * amm_spread_adjustment) / 100, 1)
        short_spread = max(
            short_spread + (short_spread * amm_spread_adjustment) / 100, 1
        )
    elif amm_spread_adjustment < 0:
        long_spread = max(long_spread - (long_spread * -amm_spread_adjustment) / 100, 1)
        short_spread = max(
            short_spread - (short_spread * -amm_spread_adjustment) / 100, 1
        )

    return long_spread, short_spread


def calculate_peg_from_target_price(
    target_price: int, base_asset_reserves: int, quote_asset_reserves: int
) -> int:
    peg_maybe = (
        ((target_price * base_asset_reserves) // quote_asset_reserves)
        + (PRICE_DIV_PEG // 2)
    ) // PRICE_DIV_PEG
    return max(peg_maybe, 1)


def calculate_bid_ask_price(
    amm: AMM,
    oracle_price_data: OraclePriceData,
    with_update: bool = True,
    is_prediction: bool = False,
) -> tuple[int, int]:
    if with_update:
        new_amm = calculate_updated_amm(amm, oracle_price_data)
    else:
        new_amm = amm

    bid_reserves, ask_reserves = calculate_spread_reserves(
        new_amm, oracle_price_data, is_prediction=is_prediction
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


def calculate_swap_output(
    input_asset_reserve: int,
    swap_amount: int,
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
    amm: AMM,
    input_asset_type: AssetType,
    swap_amount: int,
    swap_direction: SwapDirection,
):
    assert swap_amount > 0, "swap_amount must be gte 0"

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
    if is_variant(position_direction, "Long") and is_variant(input_asset_type, "BASE"):
        return SwapDirection.Remove()

    if is_variant(position_direction, "Short") and is_variant(
        input_asset_type, "QUOTE"
    ):
        return SwapDirection.Remove()

    return SwapDirection.Add()


def calculate_spread_reserves(
    amm: AMM,
    oracle_price_data: OraclePriceData,
    now: Optional[int] = None,
    is_prediction: bool = False,
) -> Tuple[int, int]:
    def calculate_spread_reserve(
        spread: int, direction: PositionDirection, amm: AMM
    ) -> dict:
        if spread == 0:
            return (int(amm.base_asset_reserve), int(amm.quote_asset_reserve))

        spread_fraction = int(spread / 2)

        # make non-zero
        if spread_fraction == 0:
            spread_fraction = 1 if spread >= 0 else -1

        # this adjusts for the differences in rounding with python int division and typescript BN division
        # because typescript BN division rounds to 0, while python int divison rounds to -infinity,
        # we have to adjust our calculation for negative numbers to avoid tiny discrepancies caused by precision loss
        if spread_fraction > 0:
            quote_asset_reserve_delta = amm.quote_asset_reserve // (
                BID_ASK_SPREAD_PRECISION // spread_fraction
            )
        else:
            div_result = BID_ASK_SPREAD_PRECISION / -spread_fraction
            div_result_rounded = (
                int(div_result) if div_result > 0 else -int(-div_result)
            )
            quote_asset_reserve_delta = -(amm.quote_asset_reserve // div_result_rounded)

        if quote_asset_reserve_delta >= 0:
            quote_asset_reserve = amm.quote_asset_reserve + abs(
                quote_asset_reserve_delta
            )
        else:
            quote_asset_reserve = amm.quote_asset_reserve - abs(
                quote_asset_reserve_delta
            )

        if is_prediction:
            qar_lower, qar_upper = get_quote_asset_reserve_prediction_market_bounds(
                amm, direction
            )
            quote_asset_reserve = clamp_num(quote_asset_reserve, qar_lower, qar_upper)

        base_asset_reserve = (amm.sqrt_k * amm.sqrt_k) // quote_asset_reserve

        return (int(base_asset_reserve), int(quote_asset_reserve))

    reserve_price = calculate_price(
        amm.base_asset_reserve, amm.quote_asset_reserve, amm.peg_multiplier
    )

    # always allow 10 bps of price offset, up to 20% of the market's max_spread
    max_offset = 0
    reference_price_offset = 0

    if amm.curve_update_intensity > 100:
        max_offset = max(
            amm.max_spread // 2,
            (PERCENTAGE_PRECISION // 10_000) * (amm.curve_update_intensity - 100),
        )

        liquidity_fraction = calculate_inventory_liquidity_ratio(
            amm.base_asset_amount_with_amm,
            amm.base_asset_reserve,
            amm.min_base_asset_reserve,
            amm.max_base_asset_reserve,
        )

        sign = sig_num(
            amm.base_asset_amount_with_amm + amm.base_asset_amount_with_unsettled_lp
        )
        liquidity_fraction_signed = liquidity_fraction * sign

        reference_price_offset = calculate_reference_price_offset(
            reserve_price,
            amm.last24h_avg_funding_rate,
            liquidity_fraction_signed,
            amm.historical_oracle_data.last_oracle_price_twap5min,
            amm.last_mark_price_twap5min,
            amm.historical_oracle_data.last_oracle_price_twap,
            amm.last_mark_price_twap,
            max_offset,
        )

    long_spread, short_spread = calculate_spread(
        amm, oracle_price_data, now, reserve_price
    )

    ask_reserves = calculate_spread_reserve(
        int(long_spread) + reference_price_offset, PositionDirection.Long(), amm
    )

    bid_reserves = calculate_spread_reserve(
        -int(short_spread) + reference_price_offset, PositionDirection.Short(), amm
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

    new_amm = deepcopy_amm(amm)
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

        new_amm = deepcopy_amm(amm)

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
    amm: AMM,
    direction: PositionDirection,
    oracle_price_data: OraclePriceData,
    is_prediction: bool = False,
):
    new_amm = calculate_updated_amm(amm, oracle_price_data)
    (long_reserves, short_reserves) = calculate_spread_reserves(
        new_amm, oracle_price_data, is_prediction=is_prediction
    )

    dir_reserves = long_reserves if is_variant(direction, "Long") else short_reserves

    return dir_reserves[0], dir_reserves[1], new_amm.sqrt_k, new_amm.peg_multiplier


def calculate_max_base_asset_amount_to_trade(
    amm: AMM,
    limit_price: int,
    direction: PositionDirection,
    oracle_price_data: OraclePriceData,
    now: Optional[int] = None,
    is_prediction: bool = False,
) -> (int, PositionDirection):
    invariant = amm.sqrt_k * amm.sqrt_k

    new_base_asset_reserve_squared = (
        ((invariant * PRICE_PRECISION) * amm.peg_multiplier) // limit_price
    ) // PEG_PRECISION

    if new_base_asset_reserve_squared < 0:
        return (0, PositionDirection.Long())

    new_base_asset_reserve = math.sqrt(new_base_asset_reserve_squared)

    short_spread_reserves, long_spread_reserves = calculate_spread_reserves(
        amm, oracle_price_data, now, is_prediction
    )

    base_asset_reserve_before = (
        long_spread_reserves[0]
        if is_variant(direction, "Long")
        else short_spread_reserves[0]
    )

    if new_base_asset_reserve > base_asset_reserve_before:
        return (
            new_base_asset_reserve - base_asset_reserve_before,
            PositionDirection.Short(),
        )
    elif new_base_asset_reserve < base_asset_reserve_before:
        return (
            base_asset_reserve_before - new_base_asset_reserve,
            PositionDirection.Long(),
        )
    else:
        print(
            "trade too small @ calculate_max_base_asset_amount_to_trade: math/amm.py:665"
        )
        return (0, PositionDirection.Long())


def get_quote_asset_reserve_prediction_market_bounds(
    amm: AMM, direction: PositionDirection
) -> Tuple[int, int]:
    quote_asset_reserve_lower_bound = 0
    peg_sqrt = math.sqrt(amm.peg_multiplier * PEG_PRECISION + 1) + 1

    quote_asset_reserve_upper_bound = (amm.sqrt_k * peg_sqrt) // amm.peg_multiplier

    if is_variant(direction, "Long"):
        quote_asset_reserve_lower_bound = (
            ((amm.sqrt_k * 22361) * peg_sqrt) // 100000
        ) // amm.peg_multiplier
    else:
        quote_asset_reserve_upper_bound = (
            ((amm.sqrt_k * 97467) * peg_sqrt) // 100000
        ) // amm.peg_multiplier

    return quote_asset_reserve_lower_bound, quote_asset_reserve_upper_bound
