from driftpy.constants.numeric_constants import BID_ASK_SPREAD_PRECISION, FIVE_MINUTE
from driftpy.types import (
    AMM,
    HistoricalOracleData,
    OracleGuardRails,
    OraclePriceData,
    PerpMarketAccount,
)


def calculate_live_oracle_twap(
    hist_oracle_data: HistoricalOracleData,
    oracle_price_data: OraclePriceData,
    now: int,
    period: int,
) -> int:
    if period == FIVE_MINUTE:
        oracle_twap = hist_oracle_data.last_oracle_price_twap5min
    else:
        oracle_twap = hist_oracle_data.last_oracle_price_twap

    since_last_update = max(1, now - hist_oracle_data.last_oracle_price_twap_ts)

    since_start = max(0, period - since_last_update)

    clamp_range = oracle_twap // 3

    clamped_oracle_price = min(
        oracle_twap + clamp_range,
        max(oracle_price_data.price, oracle_twap - clamp_range),
    )

    new_oracle_twap = (
        oracle_twap * since_start + (clamped_oracle_price * since_last_update)
    ) // (since_start + since_last_update)

    return new_oracle_twap


def calculate_live_oracle_std(
    amm: AMM, oracle_price_data: OraclePriceData, now: int
) -> int:
    since_last_update = max(
        1, now - amm.historical_oracle_data.last_oracle_price_twap_ts
    )

    since_start = max(0, amm.funding_period - since_last_update)

    live_oracle_twap = calculate_live_oracle_twap(
        amm.historical_oracle_data, oracle_price_data, now, amm.funding_period
    )

    price_delta_vs_twap = abs(oracle_price_data.price - live_oracle_twap)

    oracle_std = price_delta_vs_twap + (
        amm.oracle_std * since_start // (since_start + since_last_update)
    )

    return oracle_std


def get_new_oracle_conf_pct(
    amm: AMM, oracle_price_data: OraclePriceData, reserve_price: int, now: int
) -> int:
    conf_interval = oracle_price_data.confidence or 0

    since_last_update = max(
        0, now - amm.historical_oracle_data.last_oracle_price_twap_ts
    )

    lower_bound = amm.last_oracle_conf_pct
    if since_last_update > 0:
        lower_bound_divisor = max(21 - since_last_update, 5)
        lower_bound = amm.last_oracle_conf_pct - (
            amm.last_oracle_conf_pct // lower_bound_divisor
        )

    conf_interval_pct = (conf_interval * BID_ASK_SPREAD_PRECISION) // reserve_price

    conf_interval_pct_res = max(conf_interval_pct, lower_bound)

    return conf_interval_pct_res


def is_oracle_valid(
    market: PerpMarketAccount,
    oracle_price_data: OraclePriceData,
    oracle_guard_rails: OracleGuardRails,
    slot: int,
) -> bool:
    is_oracle_price_non_positive = oracle_price_data.price <= 0

    amm = market.amm

    lhs = (
        oracle_price_data.price
        // (max(1, amm.historical_oracle_data.last_oracle_price_twap))
    ) > oracle_guard_rails.validity.too_volatile_ratio
    rhs = (
        amm.historical_oracle_data.last_oracle_price_twap
        // (max(1, oracle_price_data.price))
    ) > oracle_guard_rails.validity.too_volatile_ratio

    is_oracle_price_too_volatile = lhs or rhs

    max_confidence_multiplier = get_max_confidence_interval_multiplier(market)

    is_confidence_too_large = (
        (max(1, oracle_price_data.confidence) * BID_ASK_SPREAD_PRECISION)
        // oracle_price_data.price
    ) > (
        oracle_guard_rails.validity.confidence_interval_max_size
        * max_confidence_multiplier
    )

    is_oracle_stale = (
        slot - oracle_price_data.slot
    ) > oracle_guard_rails.validity.slots_before_stale_for_amm

    return not (
        not oracle_price_data.has_sufficient_number_of_data_points
        or is_oracle_stale
        or is_oracle_price_non_positive
        or is_oracle_price_too_volatile
        or is_confidence_too_large
    )


def get_max_confidence_interval_multiplier(market: PerpMarketAccount) -> int:
    if str(market.contract_tier) == "ContractTier.A()":
        return 1
    elif str(market.contract_tier) == "ContractTier.B()":
        return 1
    elif str(market.contract_tier) == "ContractTier.C()":
        return 2
    elif str(market.contract_tier) == "ContractTier.Speculative()":
        return 10
    elif str(market.contract_tier) == "ContractTier.HighlySpeculative()":
        return 50
    elif str(market.contract_tier) == "ContractTier.Isolated()":
        return 50
