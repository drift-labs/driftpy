from driftpy.math.spot_market import get_token_amount
from driftpy.types import (
    OraclePriceData,
    PerpMarketAccount,
    PositionDirection,
    SpotBalanceType,
    SpotMarketAccount,
)
from driftpy.constants.numeric_constants import *


def calculate_bid_price(
    market: PerpMarketAccount, oracle_price_data: OraclePriceData
) -> int:
    from driftpy.math.amm import calculate_updated_amm_spread_reserves, calculate_price

    (
        base_asset_reserve,
        quote_asset_reserve,
        new_peg,
        _,
    ) = calculate_updated_amm_spread_reserves(
        market.amm, PositionDirection.Short(), oracle_price_data
    )

    return calculate_price(base_asset_reserve, quote_asset_reserve, new_peg)


def calculate_ask_price(
    market: PerpMarketAccount, oracle_price_data: OraclePriceData
) -> int:
    from driftpy.math.amm import calculate_updated_amm_spread_reserves, calculate_price

    (
        base_asset_reserve,
        quote_asset_reserve,
        new_peg,
        _,
    ) = calculate_updated_amm_spread_reserves(
        market.amm, PositionDirection.Long(), oracle_price_data
    )

    return calculate_price(base_asset_reserve, quote_asset_reserve, new_peg)


def calculate_net_user_pnl_imbalance(
    perp_market: PerpMarketAccount,
    spot_market: SpotMarketAccount,
    oracle_price_data: OraclePriceData,
) -> int:
    net_user_pnl = calculate_net_user_pnl(perp_market, oracle_price_data)

    pnl_pool = get_token_amount(
        perp_market.pnl_pool.scaled_balance, spot_market, SpotBalanceType.Deposit()
    )

    fee_pool = get_token_amount(
        perp_market.amm.fee_pool.scaled_balance, spot_market, SpotBalanceType.Deposit()
    )

    imbalance = net_user_pnl - (pnl_pool + fee_pool)

    return imbalance


def calculate_net_user_pnl(
    perp_market: PerpMarketAccount,
    oracle_price_data: OraclePriceData,
) -> int:
    net_user_position_value = (
        perp_market.amm.base_asset_amount_with_amm
        * oracle_price_data.price
        // BASE_PRECISION
        // PRICE_TO_QUOTE_PRECISION_RATIO
    )

    net_user_cost_basis = perp_market.amm.quote_asset_amount

    net_user_pnl = net_user_position_value + net_user_cost_basis

    return net_user_pnl
