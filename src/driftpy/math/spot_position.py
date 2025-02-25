from dataclasses import dataclass
from typing import Optional

from driftpy.constants.numeric_constants import (
    QUOTE_SPOT_MARKET_INDEX,
    SPOT_MARKET_WEIGHT_PRECISION,
)
from driftpy.math.margin import (
    MarginCategory,
    calculate_asset_weight,
    calculate_liability_weight,
)
from driftpy.math.spot_market import (
    get_signed_token_amount,
    get_token_amount,
    get_token_value,
)
from driftpy.oracles.strict_oracle_price import StrictOraclePrice
from driftpy.types import SpotMarketAccount, SpotPosition


@dataclass
class OrderFillSimulation:
    token_amount: int
    orders_value: int
    token_value: int
    weight: int
    weighted_token_value: int
    free_collateral_contribution: int


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


def get_worst_case_token_amounts(
    spot_position: SpotPosition,
    spot_market_account: SpotMarketAccount,
    strict_oracle_price: StrictOraclePrice,
    margin_category: MarginCategory,
    custom_margin_ratio: Optional[float] = None,
) -> OrderFillSimulation:
    token_amount = get_signed_token_amount(
        get_token_amount(
            spot_position.scaled_balance,
            spot_market_account,
            spot_position.balance_type,
        ),
        spot_position.balance_type,
    )

    token_value = get_strict_token_value(
        token_amount, spot_market_account.decimals, strict_oracle_price
    )

    if spot_position.open_bids == 0 and spot_position.open_asks == 0:
        weight, weighted_token_value = calculate_weighted_token_value(
            token_amount,
            token_value,
            strict_oracle_price.current,
            spot_market_account,
            margin_category,
            custom_margin_ratio,
        )

        return OrderFillSimulation(
            token_amount,
            0,
            token_value,
            weight,
            weighted_token_value,
            weighted_token_value,
        )

    bids_simulation = simulate_order_fill(
        token_amount,
        token_value,
        spot_position.open_bids,
        strict_oracle_price,
        spot_market_account,
        margin_category,
        custom_margin_ratio,
    )

    asks_simulation = simulate_order_fill(
        token_amount,
        token_value,
        spot_position.open_asks,
        strict_oracle_price,
        spot_market_account,
        margin_category,
        custom_margin_ratio,
    )

    if (
        asks_simulation.free_collateral_contribution
        < bids_simulation.free_collateral_contribution
    ):
        return asks_simulation
    else:
        return bids_simulation


def calculate_weighted_token_value(
    token_amount: int,
    token_value: int,
    oracle_price: int,
    spot_market_account: SpotMarketAccount,
    margin_category: MarginCategory,
    custom_margin_ratio: Optional[float] = None,
) -> (int, int):
    if token_value >= 0:
        weight = calculate_asset_weight(
            token_amount, oracle_price, spot_market_account, margin_category
        )
    else:
        weight = calculate_liability_weight(
            abs(token_amount), spot_market_account, margin_category
        )

    if (
        margin_category == MarginCategory.INITIAL
        and custom_margin_ratio
        and spot_market_account.market_index != QUOTE_SPOT_MARKET_INDEX
    ):
        user_custom_asset_weight = (
            max(0, SPOT_MARKET_WEIGHT_PRECISION - custom_margin_ratio)
            if token_value >= 0
            else SPOT_MARKET_WEIGHT_PRECISION + custom_margin_ratio
        )

        weight = (
            min(weight, user_custom_asset_weight)
            if token_value >= 0
            else max(weight, user_custom_asset_weight)
        )

    return (weight, (token_value * weight) // SPOT_MARKET_WEIGHT_PRECISION)


def simulate_order_fill(
    token_amount: int,
    token_value: int,
    open_orders: int,
    strict_oracle_price: StrictOraclePrice,
    spot_market: SpotMarketAccount,
    margin_category: MarginCategory,
    custom_margin_ratio: Optional[float] = None,
):
    orders_value = get_token_value(
        -open_orders, spot_market.decimals, strict_oracle_price.max()
    )
    token_amount_after_fill = token_amount + open_orders
    token_value_after_fill = token_value - orders_value

    weight, weighted_token_value_after_fill = calculate_weighted_token_value(
        token_amount_after_fill,
        token_value_after_fill,
        strict_oracle_price.current,
        spot_market,
        margin_category,
        custom_margin_ratio,
    )

    free_collateral_contribution = weighted_token_value_after_fill + orders_value

    return OrderFillSimulation(
        token_amount_after_fill,
        orders_value,
        token_value_after_fill,
        weight,
        weighted_token_value_after_fill,
        free_collateral_contribution,
    )


def is_spot_position_available(position: SpotPosition):
    return position.scaled_balance == 0 and position.open_orders == 0
