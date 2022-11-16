from driftpy.types import PositionDirection, PerpMarket, PerpPosition, SpotPosition
from driftpy.constants.numeric_constants import *
from driftpy.types import *
from driftpy.accounts import *
from driftpy.math.oracle import *
from driftpy.math.spot_market import *


def get_worst_case_token_amounts(
    position: SpotPosition,
    spot_market: SpotMarket,
    oracle_data,
):

    token_amount = get_signed_token_amount(
        get_token_amount(position.scaled_balance, spot_market, position.balance_type),
        position.balance_type,
    )

    token_all_bids = token_amount + position.open_bids
    token_all_asks = token_amount + position.open_asks

    if abs(token_all_asks) > abs(token_all_bids):
        value = get_token_value(-position.open_asks, spot_market.decimals, oracle_data)
        return [token_all_asks, value]
    else:
        value = get_token_value(-position.open_bids, spot_market.decimals, oracle_data)
        return [token_all_bids, value]


def calculate_base_asset_value_with_oracle(
    perp_position: PerpPosition, oracle_data: OracleData
):
    return (
        abs(perp_position.base_asset_amount)
        * oracle_data.price
        * QUOTE_PRECISION
        / AMM_RESERVE_PRECISION
        / PRICE_PRECISION
    )


def calculate_position_funding_pnl(market: PerpMarket, perp_position: PerpPosition):
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
    market: PerpMarket,
    perp_position: PerpPosition,
    oracle_data: OracleData,
    with_funding=False,
):
    if perp_position.base_asset_amount == 0:
        return perp_position.quote_asset_amount

    base_value = calculate_base_asset_value_with_oracle(perp_position, oracle_data)
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
