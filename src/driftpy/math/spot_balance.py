from typing import Optional, Tuple

from driftpy.constants.numeric_constants import (
    PERCENTAGE_PRECISION,
    SPOT_UTILIZATION_PRECISION,
)
from driftpy.math.margin import MarginCategory
from driftpy.math.spot_market import get_token_amount
from driftpy.math.spot_position import calculate_asset_weight
from driftpy.oracles.strict_oracle_price import StrictOraclePrice
from driftpy.types import (
    OraclePriceData,
    SpotBalanceType,
    SpotMarketAccount,
)


def get_token_value(
    token_amount: int, spot_decimals: int, oracle_price_data: OraclePriceData
) -> int:
    if token_amount == 0:
        return 0

    precision_decrease = 10**spot_decimals
    return (token_amount * oracle_price_data.price) // precision_decrease


def get_strict_token_value(
    token_amount: int, spot_decimals: int, strict_oracle_price: StrictOraclePrice
) -> int:
    if token_amount == 0:
        return 0

    if token_amount > 0:
        price = strict_oracle_price.min()
    else:
        price = strict_oracle_price.max()

    precision_decrease = 10**spot_decimals

    return (token_amount * price) // precision_decrease


def calculate_spot_market_borrow_capacity(
    market: SpotMarketAccount,
    target_borrow_rate: int,
) -> Tuple[int, int]:
    current_borrow_rate = calculate_borrow_rate(market)

    token_deposit_amount = get_token_amount(
        market.deposit_balance, market, SpotBalanceType.Deposit()
    )

    token_borrow_amount = get_token_amount(
        market.borrow_balance, market, SpotBalanceType.Borrow()
    )

    if target_borrow_rate >= market.optimal_borrow_rate:
        borrow_rate_slope = (
            (market.max_borrow_rate - market.optimal_borrow_rate)
            * SPOT_UTILIZATION_PRECISION
        ) // (SPOT_UTILIZATION_PRECISION - market.optimal_utilization)

        surplus_target_utilization = (
            (target_borrow_rate - market.optimal_borrow_rate)
            * SPOT_UTILIZATION_PRECISION
        ) // borrow_rate_slope

        target_utilization = surplus_target_utilization + market.optimal_utilization
    else:
        borrow_rate_slope = (
            market.optimal_borrow_rate * SPOT_UTILIZATION_PRECISION
        ) // market.optimal_utilization

        target_utilization = (
            target_borrow_rate * SPOT_UTILIZATION_PRECISION
        ) // borrow_rate_slope

    total_capacity = (
        token_deposit_amount * target_utilization
    ) // SPOT_UTILIZATION_PRECISION

    if current_borrow_rate >= target_borrow_rate:
        remaining_capacity = 0
    else:
        remaining_capacity = max(0, total_capacity - token_borrow_amount)

    return total_capacity, remaining_capacity


def calculate_deposit_rate(spot_market: SpotMarketAccount, delta: int = 0):
    utilization = calculate_utilization(spot_market, delta)
    borrow_rate = calculate_borrow_rate(spot_market, delta)
    deposit_rate = (
        borrow_rate
        * (PERCENTAGE_PRECISION - spot_market.insurance_fund.total_factor)
        * utilization
        // SPOT_UTILIZATION_PRECISION
        // PERCENTAGE_PRECISION
    )
    return deposit_rate


def calculate_borrow_rate(spot_market: SpotMarketAccount, delta: int = 0) -> int:
    return calculate_interest_rate(spot_market, delta)


def calculate_interest_rate(spot_market: SpotMarketAccount, delta: int = 0) -> int:
    utilization = calculate_utilization(spot_market, delta)
    if utilization > spot_market.optimal_utilization:
        surplus_utilization = utilization - spot_market.optimal_utilization
        borrow_rate_slope = (
            (spot_market.max_borrow_rate - spot_market.optimal_borrow_rate)
            * SPOT_UTILIZATION_PRECISION
        ) // (SPOT_UTILIZATION_PRECISION - spot_market.optimal_utilization)

        return spot_market.optimal_borrow_rate + (
            surplus_utilization * borrow_rate_slope // SPOT_UTILIZATION_PRECISION
        )
    else:
        borrow_rate_slope = (
            spot_market.optimal_borrow_rate * SPOT_UTILIZATION_PRECISION
        ) // spot_market.optimal_utilization

        return (utilization * borrow_rate_slope) // SPOT_UTILIZATION_PRECISION


def calculate_utilization(spot_market: SpotMarketAccount, delta: int = 0) -> int:
    token_deposit_amount = get_token_amount(
        spot_market.deposit_balance, spot_market, SpotBalanceType.Deposit()
    )
    token_borrow_amount = get_token_amount(
        spot_market.borrow_balance, spot_market, SpotBalanceType.Borrow()
    )

    if delta > 0:
        token_deposit_amount += delta
    elif delta < 0:
        token_borrow_amount += abs(delta)

    if token_borrow_amount == 0 and token_deposit_amount == 0:
        return 0
    elif token_deposit_amount == 0:
        return SPOT_UTILIZATION_PRECISION
    else:
        return int(
            (token_borrow_amount * SPOT_UTILIZATION_PRECISION) / token_deposit_amount
        )
