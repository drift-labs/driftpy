from typing import Tuple

from driftpy.math.spot_market import get_token_amount
from driftpy.oracles.strict_oracle_price import StrictOraclePrice
from driftpy.types import SpotBalanceType, SpotMarketAccount
from driftpy.constants.numeric_constants import (
    SPOT_UTILIZATION_PRECISION,
    PERCENTAGE_PRECISION,
)


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


def calculate_deposit_rate(bank: SpotMarketAccount, delta: int = 0):
    utilization = calculate_utilization(bank, delta)
    borrow_rate = calculate_borrow_rate(bank, delta)
    deposit_rate = (
        borrow_rate
        * (PERCENTAGE_PRECISION - bank.insurance_fund.total_factor)
        * utilization
        // SPOT_UTILIZATION_PRECISION
        // PERCENTAGE_PRECISION
    )
    return deposit_rate


def calculate_borrow_rate(bank: SpotMarketAccount, delta: int = 0) -> int:
    return calculate_interest_rate(bank, delta)


def calculate_interest_rate(bank: SpotMarketAccount, delta: int = 0) -> int:
    utilization = calculate_utilization(bank, delta)
    if utilization > bank.optimal_utilization:
        surplus_utilization = utilization - bank.optimal_utilization
        borrow_rate_slope = (
            (bank.max_borrow_rate - bank.optimal_borrow_rate)
            * SPOT_UTILIZATION_PRECISION
        ) // (SPOT_UTILIZATION_PRECISION - bank.optimal_utilization)

        return bank.optimal_borrow_rate + (
            surplus_utilization * borrow_rate_slope // SPOT_UTILIZATION_PRECISION
        )
    else:
        borrow_rate_slope = (
            bank.optimal_borrow_rate * SPOT_UTILIZATION_PRECISION
        ) // bank.optimal_utilization

        return (utilization * borrow_rate_slope) // SPOT_UTILIZATION_PRECISION


def calculate_utilization(bank: SpotMarketAccount, delta: int = 0) -> int:
    token_deposit_amount = get_token_amount(
        bank.deposit_balance, bank, SpotBalanceType.Deposit()
    )
    token_borrow_amount = get_token_amount(
        bank.borrow_balance, bank, SpotBalanceType.Borrow()
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
