from driftpy.constants.numeric_constants import *
from driftpy.types import *
from driftpy.accounts import *
from driftpy.math.oracle import OracleData
from driftpy.math.spot_market import *

from enum import Enum


def calculate_size_discount_asset_weight(
    size,
    imf_factor,
    asset_weight,
):
    if imf_factor == 0:
        return asset_weight

    size_sqrt = int((size * 10) ** 0.5) + 1
    imf_num = SPOT_IMF_PRECISION + (SPOT_IMF_PRECISION / 10)

    size_discount_asset_weight = (
        imf_num
        * SPOT_WEIGHT_PRECISION
        / (SPOT_IMF_PRECISION + size_sqrt * imf_factor / 100_000)
    )

    min_asset_weight = min(asset_weight, size_discount_asset_weight)
    return min_asset_weight


class MarginCategory(Enum):
    INITIAL = "Initial"
    MAINTENANCE = "Maintenance"


def calculate_asset_weight(
    amount,
    spot_market: SpotMarket,
    margin_category: MarginCategory,
):
    size_precision = 10 ** spot_market.decimals

    if size_precision > AMM_RESERVE_PRECISION:
        size_in_amm_precision = amount / (size_precision / AMM_RESERVE_PRECISION)
    else:
        size_in_amm_precision = amount * AMM_RESERVE_PRECISION / size_precision

    match margin_category:
        case MarginCategory.INITIAL:
            asset_weight = calculate_size_discount_asset_weight(
                size_in_amm_precision,
                spot_market.imf_factor,
                spot_market.initial_asset_weight,
            )
        case MarginCategory.MAINTENANCE:
            asset_weight = spot_market.maintenance_asset_weight 
            # calculate_size_discount_asset_weight(
            #     size_in_amm_precision,
            #     spot_market.imf_factor,
            #     spot_market.maintenance_asset_weight,
            # )
        case None:
            asset_weight = spot_market.initial_asset_weight
        case _:
            raise Exception(f"Invalid margin category: {margin_category}")

    return asset_weight


def calculate_size_premium_liability_weight(
    size: int, imf_factor: int, liability_weight: int, precision: int
) -> int:
    if imf_factor == 0:
        return liability_weight

    size_sqrt = int((size * 10 + 1) ** 0.5)
    denom0 = max(1, SPOT_IMF_PRECISION / imf_factor)
    assert denom0 > 0
    liability_weight_numerator = liability_weight - (liability_weight / denom0)

    denom = 100_000 * SPOT_IMF_PRECISION / precision
    assert denom > 0

    size_premium_liability_weight = liability_weight_numerator + (
        size_sqrt * imf_factor / denom
    )
    max_liability_weight = max(liability_weight, size_premium_liability_weight)
    return max_liability_weight

def calculate_net_user_pnl(
    perp_market: PerpMarket, 
    oracle_data: OracleData
):
    net_user_position_value = (
        perp_market.amm.base_asset_amount_with_amm
        * oracle_data.price
        / BASE_PRECISION
        / PRICE_TO_QUOTE_PRECISION_RATIO
    )

    net_user_cost_basis = perp_market.amm.quote_asset_amount
    net_user_pnl = net_user_position_value + net_user_cost_basis

    return net_user_pnl

def calculate_net_user_pnl_imbalance(
    perp_market: PerpMarket, 
    spot_market: SpotMarket, 
    oracle_data: OracleData
):
    user_pnl = calculate_net_user_pnl(
        perp_market, oracle_data
    )

    pnl_pool = get_token_amount(
        perp_market.pnl_pool.scaled_balance, 
        spot_market, 
        "SpotBalanceType.Deposit()"
    )

    imbalance = user_pnl - pnl_pool
    return imbalance

def calculate_unrealized_asset_weight(
    perp_market: PerpMarket, 
    spot_market: SpotMarket, 
    unrealized_pnl: int, 
    margin_category: MarginCategory, 
    oracle_data: OracleData
):
    match margin_category:
        case MarginCategory.INITIAL:
            asset_weight = perp_market.unrealized_pnl_initial_asset_weight
            if perp_market.unrealized_pnl_max_imbalance > 0: 
                net_unsettled_pnl = calculate_net_user_pnl_imbalance(
                    perp_market, 
                    spot_market, 
                    oracle_data
                )
                if net_unsettled_pnl > perp_market.unrealized_pnl_max_imbalance:
                    asset_weight = asset_weight * perp_market.unrealized_pnl_max_imbalance / net_unsettled_pnl
                
            asset_weight = calculate_size_discount_asset_weight(
                unrealized_pnl, 
                perp_market.unrealized_pnl_imf_factor, 
                asset_weight
            )
        case MarginCategory.MAINTENANCE:
            asset_weight = perp_market.unrealized_pnl_maintenance_asset_weight
        case _: 
            raise Exception(f"invalid margin category: {margin_category}")

    return asset_weight

def calculate_liability_weight(
    balance_amount: int, spot_market: SpotMarket, margin_category: MarginCategory
) -> int:
    size_precision = 10 ** spot_market.decimals
    if size_precision > AMM_RESERVE_PRECISION:
        size_in_amm_reserve_precision = balance_amount / (
            size_precision / AMM_RESERVE_PRECISION
        )
    else:
        size_in_amm_reserve_precision = (
            balance_amount * AMM_RESERVE_PRECISION / size_precision
        )

    match margin_category:
        case MarginCategory.INITIAL:
            asset_weight = calculate_size_premium_liability_weight(
                size_in_amm_reserve_precision,
                spot_market.imf_factor,
                spot_market.initial_liability_weight,
                SPOT_WEIGHT_PRECISION,
            )
        case MarginCategory.MAINTENANCE:
            asset_weight = calculate_size_premium_liability_weight(
                size_in_amm_reserve_precision,
                spot_market.imf_factor,
                spot_market.maintenance_liability_weight,
                SPOT_WEIGHT_PRECISION,
            )
        case _:
            asset_weight = spot_market.initial_liability_weight

    return asset_weight


def get_spot_asset_value(
    amount: int, oracle_data, spot_market: SpotMarket, margin_category: MarginCategory
):
    asset_value = get_token_value(amount, spot_market.decimals, oracle_data)

    if margin_category is not None:
        weight = calculate_asset_weight(amount, spot_market, margin_category)
        asset_value = asset_value * weight / SPOT_WEIGHT_PRECISION

    return asset_value


def calculate_market_margin_ratio(
    market: PerpMarket, size: int, margin_category: MarginCategory
) -> int:
    match margin_category:
        case MarginCategory.INITIAL:
            margin_ratio = calculate_size_premium_liability_weight(
                size, market.imf_factor, market.margin_ratio_initial, MARGIN_PRECISION
            )
        case MarginCategory.MAINTENANCE:
            margin_ratio = calculate_size_premium_liability_weight(
                size,
                market.imf_factor,
                market.margin_ratio_maintenance,
                MARGIN_PRECISION,
            )
    return margin_ratio


def get_spot_liability_value(
    token_amount: int,
    oracle_data: OracleData,
    spot_market: SpotMarket,
    margin_category: MarginCategory,
    liquidation_buffer: int = None,
    max_margin_ratio: int = None,
) -> int:
    liability_value = get_token_value(token_amount, spot_market.decimals, oracle_data)

    if margin_category is not None:
        weight = calculate_liability_weight(token_amount, spot_market, margin_category)

        if margin_category == MarginCategory.INITIAL:
            if max_margin_ratio:
                weight = max(weight, max_margin_ratio)

        if liquidation_buffer is not None:
            weight += liquidation_buffer

        liability_value = liability_value * weight / SPOT_WEIGHT_PRECISION

    return liability_value
