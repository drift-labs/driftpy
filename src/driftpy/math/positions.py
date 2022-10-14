from driftpy.types import PositionDirection, PerpMarket, PerpPosition, SpotPosition

from driftpy.math.amm import calculate_amm_reserves_after_swap, get_swap_direction
from driftpy.constants.numeric_constants import (
    PRICE_PRECISION as PRICE_PRECISION,
    AMM_RESERVE_PRECISION,
    FUNDING_RATE_BUFFER,
    PRICE_TO_QUOTE_PRECISION_RATIO,
    AMM_TO_QUOTE_PRECISION_RATIO,
    AMM_TIMES_PEG_TO_QUOTE_PRECISION_RATIO,
)

from driftpy.math.amm import AssetType


def is_spot_position_available(position: SpotPosition):
    return position.scaled_balance == 0 and position.open_orders == 0


def is_available(position: PerpPosition):
    return (
        position.base_asset_amount == 0
        and position.quote_asset_amount == 0
        and position.open_orders == 0
        and position.lp_shares == 0
    )


def calculate_base_asset_value(market: PerpMarket, user_position: PerpPosition) -> int:

    if user_position.base_asset_amount == 0:
        return 0

    direction_to_close = (
        PositionDirection.SHORT
        if user_position.base_asset_amount > 0
        else PositionDirection.LONG
    )

    new_quote_asset_reserve, _ = calculate_amm_reserves_after_swap(
        market.amm,
        AssetType.BASE,
        abs(user_position.base_asset_amount),
        get_swap_direction(AssetType.BASE, direction_to_close),
    )

    result = None
    if direction_to_close == PositionDirection.SHORT:
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
    market: PerpMarket, market_position: PerpPosition, with_funding=False
):
    pnl = 0.0

    if market_position.base_asset_amount == 0:
        return pnl

    base_asset_value = calculate_base_asset_value(market, market_position)

    if market_position.base_asset_amount > 0:
        pnl = base_asset_value - market_position.quote_asset_amount
    else:
        pnl = market_position.quote_asset_amount - base_asset_value

    if with_funding:
        funding_rate_pnl = 0.0
        pnl += funding_rate_pnl / float(PRICE_TO_QUOTE_PRECISION_RATIO)

    return pnl


def calculate_position_funding_pnl(market: PerpMarket, market_position: PerpPosition):
    funding_pnl = 0.0

    if market_position.base_asset_amount == 0:
        return funding_pnl

    amm_cum_funding_rate = (
        market.amm.cumulative_funding_rate_long
        if market_position.base_asset_amount > 0
        else market.amm.cumulative_funding_rate_short
    )

    funding_pnl = (
        market_position.last_cumulative_funding_rate - amm_cum_funding_rate
    ) * market_position.base_asset_amount

    funding_pnl /= float(AMM_RESERVE_PRECISION * FUNDING_RATE_BUFFER)

    return funding_pnl


def calculate_entry_price(market_position: PerpPosition):
    if market_position.base_asset_amount == 0:
        return 0

    return abs(
        market_position.quote_asset_amount
        * PRICE_PRECISION
        * AMM_TO_QUOTE_PRECISION_RATIO
        / market_position.base_asset_amount
    )
