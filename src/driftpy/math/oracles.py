from driftpy.constants.numeric_constants import FIVE_MINUTE
from driftpy.types import AMM, HistoricalOracleData, OraclePriceData


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
