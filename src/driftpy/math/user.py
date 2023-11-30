from driftpy.types import (
    UserAccount,
    PerpPosition,
    PerpMarketAccount,
)
from collections.abc import Mapping

from driftpy.math.market import calculate_mark_price
from driftpy.math.perp_position import (
    calculate_position_pnl,
    calculate_base_asset_value,
)
from driftpy.constants.numeric_constants import (
    AMM_RESERVE_PRECISION,
)
import numpy as np


def calculate_unrealised_pnl(
    user_position: list[PerpPosition],
    markets: Mapping[int, PerpMarketAccount],
    market_index: int = None,
) -> int:
    pnl = 0
    for position in user_position:
        if position.base_asset_amount != 0:
            if market_index is None or position.market_index == int(market_index):
                market = markets[position.market_index]
                pnl += calculate_position_pnl(market, position)

    return pnl


def get_total_position_value(
    user_position: list[PerpPosition],
    markets: Mapping[int, PerpMarketAccount],
):
    value = 0
    for position in user_position:
        market = markets[position.market_index]
        value += calculate_base_asset_value(market, position)

    return value


def get_position_value(
    user_position: list[PerpPosition],
    markets: Mapping[int, PerpMarketAccount],
    market_index: int,
):
    assert market_index is None or int(market_index) >= 0
    value = 0
    for position in user_position:
        if position.base_asset_amount != 0:
            if market_index is None or position.market_index == int(market_index):
                market = markets[position.market_index]
                value += calculate_base_asset_value(market, position)
    return value


def get_total_collateral(
    user_account: UserAccount, markets: Mapping[int, PerpMarketAccount]
):
    collateral = user_account.collateral
    return collateral + calculate_unrealised_pnl(user_account.positions, markets)


def get_margin_ratio(
    user_account: UserAccount, markets: Mapping[int, PerpMarketAccount]
):
    tpv = get_total_position_value(user_account.positions, markets)
    if tpv > 0:
        return get_total_collateral(user_account, markets) / tpv
    else:
        return np.nan


def get_leverage(user_account: UserAccount, markets: Mapping[int, PerpMarketAccount]):
    return get_total_position_value(
        user_account.positions, markets
    ) / get_total_collateral(user_account, markets)


def get_free_collateral(
    user_account: UserAccount, markets: Mapping[int, PerpMarketAccount]
):
    return get_total_collateral(user_account, markets) - (
        get_margin_requirement(user_account.positions, markets, "initial")
    )


def get_margin_requirement(
    user_position: list[PerpPosition],
    markets: Mapping[int, PerpMarketAccount],
    kind: str,
):
    assert kind in ["initial", "partial", "maintenance"]

    positions_account = user_position
    value = 0
    for position in positions_account:
        if position.base_asset_amount != 0:
            market = markets[position.market_index]
            mr = None
            if kind == "partial":
                mr = market.margin_ratio_partial
            elif kind == "initial":
                mr = market.margin_ratio_initial
            else:
                mr = market.margin_ratio_maintenance
            value += calculate_base_asset_value(market, position) * (mr / 10000)
    return value


def can_be_liquidated(
    user_account: UserAccount, markets: Mapping[int, PerpMarketAccount]
):
    return get_total_collateral(user_account, markets) < (
        get_margin_requirement("partial")
    )


def liquidation_price(
    user_account: UserAccount,
    markets: Mapping[int, PerpMarketAccount],
    market_index: int,
):
    # todo

    tc = get_total_collateral(user_account, markets)
    tpv = get_total_position_value(user_account.positions, markets)
    free_collateral = get_free_collateral(user_account, markets)

    # todo: use maint/partial lev
    partial_lev = 16
    # maint_lev = 20

    lev = partial_lev  # todo: param

    # this_level = partial_lev #if partial else maint_lev

    market = markets[market_index]

    position = user_account.positions
    if position.base_asset_amount > 0 and tpv < free_collateral:
        return -1

    price_delt = None
    if position.base_asset_amount > 0:
        price_delt = tc * lev - tpv / (lev - 1)
    else:
        price_delt = tc * lev - tpv / (lev + 1)

    current_price = calculate_mark_price(market)

    eat_margin = price_delt * AMM_RESERVE_PRECISION / position.base_asset_amount
    if eat_margin > current_price:
        return -1

    liq_price = current_price - eat_margin

    return liq_price
