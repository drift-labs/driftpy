from driftpy.math.spot_market import *
from driftpy.types import OraclePriceData, is_variant
from driftpy.constants.numeric_constants import *
from driftpy.math.amm import calculate_amm_reserves_after_swap, get_swap_direction


def calculate_base_asset_value_with_oracle(
    market: PerpMarketAccount,
    perp_position: PerpPosition,
    oracle_price_data: OraclePriceData,
    include_open_orders: bool = False,
):
    price = oracle_price_data.price

    if is_variant(market.status, "Settlement"):
        price = market.expiry_price

    baa = (
        calculate_worst_case_base_asset_amount(perp_position)
        if include_open_orders
        else perp_position.base_asset_amount
    )

    return (abs(baa) * price) // AMM_RESERVE_PRECISION


def calculate_position_funding_pnl(
    market: PerpMarketAccount, perp_position: PerpPosition
):
    if perp_position.base_asset_amount == 0:
        return 0

    amm_cumm_funding_rate = (
        market.amm.cumulative_funding_rate_long
        if perp_position.base_asset_amount > 0
        else market.amm.cumulative_funding_rate_short
    )

    funding_rate_pnl = (
        (amm_cumm_funding_rate - perp_position.last_cumulative_funding_rate)
        * perp_position.base_asset_amount
        / AMM_RESERVE_PRECISION
        / FUNDING_RATE_BUFFER
        * -1
    )

    return funding_rate_pnl


def calculate_position_pnl_with_oracle(
    market: PerpMarketAccount,
    perp_position: PerpPosition,
    oracle_data: OraclePriceData,
    with_funding=False,
):
    if perp_position.base_asset_amount == 0:
        return perp_position.quote_asset_amount

    base_value = calculate_base_asset_value_with_oracle(
        market, perp_position, oracle_data
    )
    base_asset_sign = -1 if perp_position.base_asset_amount < 0 else 1
    pnl = base_value * base_asset_sign + perp_position.quote_asset_amount

    if with_funding:
        funding_pnl = calculate_position_funding_pnl(market, perp_position)
        pnl += funding_pnl

    return pnl


def calculate_worst_case_base_asset_amount(perp_position: PerpPosition):
    all_bids = perp_position.base_asset_amount + perp_position.open_bids
    all_asks = perp_position.base_asset_amount + perp_position.open_asks
    if abs(all_bids) > abs(all_asks):
        return all_bids
    else:
        return all_asks


def is_available(position: PerpPosition):
    return (
        position.base_asset_amount == 0
        and position.quote_asset_amount == 0
        and position.open_orders == 0
        and position.lp_shares == 0
    )


def calculate_base_asset_value(
    market: PerpMarketAccount, user_position: PerpPosition
) -> int:
    if user_position.base_asset_amount == 0:
        return 0

    direction_to_close = (
        PositionDirection.Short()
        if user_position.base_asset_amount > 0
        else PositionDirection.Long()
    )

    new_quote_asset_reserve, _ = calculate_amm_reserves_after_swap(
        market.amm,
        AssetType.BASE(),
        abs(user_position.base_asset_amount),
        get_swap_direction(AssetType.BASE(), direction_to_close),
    )

    result = None
    if direction_to_close == PositionDirection.Short():
        result = (
            (market.amm.quote_asset_reserve - new_quote_asset_reserve)
            * market.amm.peg_multiplier
        ) / AMM_TIMES_PEG_TO_QUOTE_PRECISION_RATIO
    else:
        # PositionDirection.LONG:
        result = (
            (
                (new_quote_asset_reserve - market.amm.quote_asset_reserve)
                * market.amm.peg_multiplier
            )
            / AMM_TIMES_PEG_TO_QUOTE_PRECISION_RATIO
        ) + 1.0

    return result


def calculate_position_pnl(
    market: PerpMarketAccount,
    perp_position: PerpPosition,
    oracle_price_data: OraclePriceData,
    with_funding: bool = False,
):
    if perp_position.base_asset_amount == 0:
        return perp_position.quote_asset_amount

    base_asset_value = calculate_base_asset_value_with_oracle(
        market, perp_position, oracle_price_data
    )

    sign = -1 if perp_position.base_asset_amount < 0 else 1

    pnl = base_asset_value * sign + perp_position.quote_asset_amount

    if with_funding:
        funding_rate_pnl = calculate_position_funding_pnl(market, perp_position)

        pnl += funding_rate_pnl

    return pnl


def calculate_entry_price(market_position: PerpPosition):
    if market_position.base_asset_amount == 0:
        return 0

    return abs(
        market_position.quote_entry_amount
        * PRICE_PRECISION
        * AMM_TO_QUOTE_PRECISION_RATIO
        / market_position.base_asset_amount
    )
