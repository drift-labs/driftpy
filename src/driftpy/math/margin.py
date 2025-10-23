import math
from enum import Enum

from driftpy.constants.numeric_constants import (
    AMM_RESERVE_PRECISION,
    BASE_PRECISION,
    MARGIN_PRECISION,
    PERCENTAGE_PRECISION,
    PRICE_TO_QUOTE_PRECISION_RATIO,
    SPOT_IMF_PRECISION,
    SPOT_WEIGHT_PRECISION,
)
from driftpy.math.spot_market import get_token_amount, get_token_value
from driftpy.types import (
    OraclePriceData,
    PerpMarketAccount,
    SpotBalanceType,
    SpotMarketAccount,
    is_variant,
)


def calculate_size_discount_asset_weight(
    size: int,
    imf_factor: int,
    asset_weight: int,
) -> int:
    if imf_factor == 0:
        return asset_weight

    size_sqrt = math.ceil((abs(size) * 10) ** 0.5) + 1
    imf_num = SPOT_IMF_PRECISION + (SPOT_IMF_PRECISION / 10)

    size_discount_asset_weight = math.ceil(
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
    amount: int,
    oracle_price: int,
    spot_market: SpotMarketAccount,
    margin_category: MarginCategory,
):
    size_precision = 10**spot_market.decimals

    if size_precision > AMM_RESERVE_PRECISION:
        size_in_amm_precision = amount / (size_precision / AMM_RESERVE_PRECISION)
    else:
        size_in_amm_precision = amount * AMM_RESERVE_PRECISION / size_precision

    match margin_category:
        case MarginCategory.INITIAL:
            asset_weight = calculate_size_discount_asset_weight(
                size_in_amm_precision,
                spot_market.imf_factor,
                calculate_scaled_initial_asset_weight(spot_market, oracle_price),
            )
        case MarginCategory.MAINTENANCE:
            asset_weight = calculate_size_discount_asset_weight(
                size_in_amm_precision,
                spot_market.imf_factor,
                spot_market.maintenance_asset_weight,
            )
        case None:
            asset_weight = calculate_scaled_initial_asset_weight(
                spot_market, oracle_price
            )
        case _:
            raise Exception(f"Invalid margin category: {margin_category}")

    return asset_weight


def calculate_scaled_initial_asset_weight(
    spot_market: SpotMarketAccount, oracle_price: int
) -> int:
    if spot_market.scale_initial_asset_weight_start == 0:
        return spot_market.initial_asset_weight

    deposits = get_token_amount(
        spot_market.deposit_balance,
        spot_market,
        SpotBalanceType.Deposit(),  # type: ignore
    )

    deposits_value = get_token_value(deposits, spot_market.decimals, oracle_price)

    if deposits_value < spot_market.scale_initial_asset_weight_start:
        return spot_market.initial_asset_weight
    else:
        return (
            spot_market.initial_asset_weight
            * spot_market.scale_initial_asset_weight_start
            // deposits_value
        )


def calculate_size_premium_liability_weight(
    size: int,
    imf_factor: int,
    liability_weight: int,
    precision: int,
    is_bounded: bool = True,
) -> int:
    if imf_factor == 0:
        return liability_weight

    size = abs(size) * 10 + 1
    size_sqrt = size**0.5

    liability_weight_numerator = liability_weight - (liability_weight // 5)

    denom = (100_000 * SPOT_IMF_PRECISION) // precision
    assert denom > 0

    size_premium_liability_weight = liability_weight_numerator + (
        (size_sqrt * imf_factor) // denom
    )

    if is_bounded:
        return max(liability_weight, size_premium_liability_weight)
    else:
        return size_premium_liability_weight


def calc_high_leverage_mode_initial_margin_ratio_from_size(
    pre_size_adj_margin_ratio: int,
    size_adj_margin_ratio: int,
    default_margin_ratio: int,
) -> int:
    if size_adj_margin_ratio < pre_size_adj_margin_ratio:
        denom_component = max(pre_size_adj_margin_ratio // 5, 1)
        size_pct_discount_factor = PERCENTAGE_PRECISION - (
            (pre_size_adj_margin_ratio - size_adj_margin_ratio)
            * PERCENTAGE_PRECISION
            // denom_component
        )

        hlm_margin_delta = max(pre_size_adj_margin_ratio - default_margin_ratio, 1)
        hlm_margin_delta_proportion = (
            hlm_margin_delta * size_pct_discount_factor
        ) // PERCENTAGE_PRECISION

        return hlm_margin_delta_proportion + default_margin_ratio
    elif size_adj_margin_ratio == pre_size_adj_margin_ratio:
        return default_margin_ratio
    else:
        return size_adj_margin_ratio


def calculate_net_user_pnl(
    perp_market: PerpMarketAccount, oracle_data: OraclePriceData
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
    perp_market: PerpMarketAccount,
    spot_market: SpotMarketAccount,
    oracle_data: OraclePriceData,
):
    user_pnl = calculate_net_user_pnl(perp_market, oracle_data)

    pnl_pool = get_token_amount(
        perp_market.pnl_pool.scaled_balance,
        spot_market,
        SpotBalanceType.Deposit(),  # type: ignore
    )

    imbalance = user_pnl - pnl_pool
    return imbalance


def calculate_unrealized_asset_weight(
    perp_market: PerpMarketAccount,
    spot_market: SpotMarketAccount,
    unrealized_pnl: int,
    margin_category: MarginCategory,
    oracle_data: OraclePriceData,
):
    match margin_category:
        case MarginCategory.INITIAL:
            asset_weight = perp_market.unrealized_pnl_initial_asset_weight
            if perp_market.unrealized_pnl_max_imbalance > 0:
                net_unsettled_pnl = calculate_net_user_pnl_imbalance(
                    perp_market, spot_market, oracle_data
                )
                if net_unsettled_pnl > perp_market.unrealized_pnl_max_imbalance:
                    asset_weight = (
                        asset_weight
                        * perp_market.unrealized_pnl_max_imbalance
                        / net_unsettled_pnl
                    )

            asset_weight = calculate_size_discount_asset_weight(
                unrealized_pnl, perp_market.unrealized_pnl_imf_factor, asset_weight
            )
        case MarginCategory.MAINTENANCE:
            asset_weight = perp_market.unrealized_pnl_maintenance_asset_weight
        case _:
            raise Exception(f"invalid margin category: {margin_category}")

    return asset_weight


def calculate_liability_weight(
    balance_amount: int, spot_market: SpotMarketAccount, margin_category: MarginCategory
) -> int:
    size_precision = 10**spot_market.decimals
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


def calculate_market_margin_ratio(
    market: PerpMarketAccount,
    size: int,
    margin_category: MarginCategory,
    custom_margin_ratio: int = 0,
    user_high_leverage_mode: bool = False,
) -> int:
    if is_variant(market.status, "Settlement"):
        return 0

    is_high_leverage_user = (
        user_high_leverage_mode
        and market.high_leverage_margin_ratio_initial > 0
        and market.high_leverage_margin_ratio_maintenance > 0
    )

    margin_ratio_initial_default = (
        market.high_leverage_margin_ratio_initial
        if is_high_leverage_user
        else market.margin_ratio_initial
    )
    margin_ratio_maintenance_default = (
        market.high_leverage_margin_ratio_maintenance
        if is_high_leverage_user
        else market.margin_ratio_maintenance
    )

    if margin_category == MarginCategory.INITIAL:
        default_margin_ratio = margin_ratio_initial_default
    elif margin_category == MarginCategory.MAINTENANCE:
        default_margin_ratio = margin_ratio_maintenance_default
    else:
        raise Exception("Invalid margin category")

    if is_high_leverage_user and margin_category != MarginCategory.MAINTENANCE:
        # Use ordinary-mode ratios for size-adjusted calc
        pre_size_adj_margin_ratio = market.margin_ratio_initial

        size_adj_margin_ratio = calculate_size_premium_liability_weight(
            size,
            market.imf_factor,
            pre_size_adj_margin_ratio,
            MARGIN_PRECISION,
            False,
        )

        margin_ratio = calc_high_leverage_mode_initial_margin_ratio_from_size(
            pre_size_adj_margin_ratio,
            size_adj_margin_ratio,
            default_margin_ratio,
        )
    else:
        size_adj_margin_ratio = calculate_size_premium_liability_weight(
            size,
            market.imf_factor,
            default_margin_ratio,
            MARGIN_PRECISION,
            True,
        )
        margin_ratio = max(default_margin_ratio, size_adj_margin_ratio)

    if margin_category == MarginCategory.INITIAL:
        margin_ratio = max(margin_ratio, custom_margin_ratio)

    return margin_ratio
