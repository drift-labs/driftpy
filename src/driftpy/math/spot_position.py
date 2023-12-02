from dataclasses import dataclass

from driftpy.constants import SPOT_WEIGHT_PRECISION
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
from driftpy.types import SpotPosition, SpotMarketAccount, OraclePriceData


@dataclass
class OrderFillSimulation:
    token_amount: int
    orders_value: int
    token_value: int
    weight: int
    weighted_token_value: int
    free_collateral_contribution: int


def get_worst_case_token_amounts(
    spot_position: SpotPosition,
    spot_market_account: SpotMarketAccount,
    oracle_price_data: OraclePriceData,
    margin_category: MarginCategory = MarginCategory.INITIAL,
) -> OrderFillSimulation:
    token_amount = get_signed_token_amount(
        get_token_amount(
            spot_position.scaled_balance,
            spot_market_account,
            spot_position.balance_type,
        ),
        spot_position.balance_type,
    )

    token_value = get_token_value(
        token_amount, spot_market_account.decimals, oracle_price_data
    )

    if spot_position.open_bids == 0 and spot_position.open_asks == 0:
        weight, weighted_token_value = calculate_weighted_token_value(
            token_amount,
            token_value,
            oracle_price_data.price,
            spot_market_account,
            margin_category,
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
        oracle_price_data,
        spot_market_account,
        margin_category,
    )

    asks_simulation = simulate_order_fill(
        token_amount,
        token_value,
        spot_position.open_asks,
        oracle_price_data,
        spot_market_account,
        margin_category,
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
) -> (int, int):
    if token_value >= 0:
        weight = calculate_asset_weight(
            token_amount, oracle_price, spot_market_account, margin_category
        )
    else:
        weight = calculate_liability_weight(
            token_amount, spot_market_account, margin_category
        )

    weighted_token_value = token_value * weight // SPOT_WEIGHT_PRECISION

    return weight, weighted_token_value


def simulate_order_fill(
    token_amount: int,
    token_value: int,
    open_orders: int,
    oracle_price_data: OraclePriceData,
    spot_market: SpotMarketAccount,
    margin_category: MarginCategory,
):
    orders_value = get_token_value(
        -open_orders, spot_market.decimals, oracle_price_data
    )
    token_amount_after_fill = token_amount + open_orders
    token_value_after_fill = token_value - orders_value

    weight, weighted_token_value_after_fill = calculate_weighted_token_value(
        token_amount_after_fill,
        token_value_after_fill,
        oracle_price_data.price,
        spot_market,
        margin_category,
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
