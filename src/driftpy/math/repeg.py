
from driftpy.math.amm import calculate_terminal_price, calculate_budgeted_repeg
from driftpy.math.trade import (
    calculate_trade_slippage,
    calculate_target_price_trade,
    calculate_trade_acquired_amounts,
)
from driftpy.math.positions import calculate_base_asset_value, calculate_position_pnl
from driftpy.types import PositionDirection, AssetType, MarketPosition
from driftpy.math.market import calculate_mark_price
from driftpy.constants.numeric_constants import (
    AMM_TIMES_PEG_TO_QUOTE_PRECISION_RATIO,
    PEG_PRECISION,
)
from solana.publickey import PublicKey
import copy

import numpy as np


def get_optimal_peg(market, target_px):
    old_mark = calculate_mark_price(market)
    peg_adj = (old_mark - target_px) * 1e3 - 1  # *repeg_direction
    peg_adj *= market.amm.base_asset_reserve / market.amm.quote_asset_reserve
    peg_adj /= 10
    new_peg = market.amm.peg_multiplier - peg_adj
    return new_peg


def calculate_curve_op_cost(market, market_index, base_p, quote_p, new_peg=None):
    #     print(market)
    # print(base_p, quote_p)
    if not (base_p > 0 and quote_p > 0):
        print(base_p, quote_p)
        assert False
    net_user_position = MarketPosition(
        market_index,
        market.base_asset_amount,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        PublicKey(0),
        0,
        0,
    )

    current_value = calculate_base_asset_value(market, net_user_position)

    marketNewK = copy.deepcopy(market)
    marketNewK.amm.base_asset_reserve *= base_p
    marketNewK.amm.quote_asset_reserve *= quote_p
    if new_peg is not None:
        # print('Alter Peg', new_peg)
        marketNewK.amm.peg_multiplier = new_peg

    marketNewK.amm.sqrt_k = np.sqrt(
        marketNewK.amm.base_asset_reserve * marketNewK.amm.quote_asset_reserve
    )

    net_user_position.quote_asset_amount = current_value

    # print(marketNewK.amm.base_asset_reserve, net_user_position.base_asset_amount)
    cost = calculate_position_pnl(marketNewK, net_user_position, False)
    # print(cost)

    old_price = calculate_mark_price(market)
    new_price = calculate_mark_price(marketNewK)
    # print('mark price:', old_price, '->', new_price, '(%.5f pct)' % ((old_price/new_price - 1)*100))

    old_price = calculate_terminal_price(market)
    new_price = calculate_terminal_price(marketNewK)
    # print('terminal price:', old_price, '->', new_price, '(%.5f pct)' % ((old_price/new_price - 1)*100))

    # print('sqrt k:', market.amm.sqrt_k/1e13, '->', marketNewK.amm.sqrt_k/1e13)

    return cost / 1e6, marketNewK


def calculate_rebalance_market(market, market_index):
    new_peg = calculate_terminal_price(market) * 1e3
    cur_mark = calculate_mark_price(market)
    net_user_position = MarketPosition(
        market_index,
        market.base_asset_amount,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        PublicKey(0),
        0,
        0,
    )

    cur_base_terminal = market.amm.base_asset_reserve + market.base_asset_amount
    cur_quote_terminal = market.amm.sqrt_k ** 2 / cur_base_terminal

    newSqrtK = 0
    if new_peg < market.amm.peg_multiplier:
        newSqrtK = cur_base_terminal
    else:
        newSqrtK = cur_quote_terminal
    newSqrtK = np.sqrt(cur_quote_terminal * cur_base_terminal)

    marketNewPeg = copy.deepcopy(market)

    marketNewPeg.amm.base_asset_reserve = newSqrtK - marketNewPeg.base_asset_amount
    marketNewPeg.amm.quote_asset_reserve = (
        newSqrtK ** 2 / marketNewPeg.amm.base_asset_reserve
    )
    marketNewPeg.amm.sqrt_k = newSqrtK
    marketNewPeg.amm.peg_multiplier = new_peg

    current_value = calculate_base_asset_value(market, net_user_position)
    net_user_position.quote_asset_amount = current_value
    cost = calculate_position_pnl(market, net_user_position, False)
    assert abs(cost) < 1e-6
    print(cur_mark, calculate_mark_price(marketNewPeg))
    assert abs(cur_mark - calculate_mark_price(marketNewPeg)) < 1e-3
    return marketNewPeg


def calculate_buyout_cost(market, market_index, new_peg, sqrt_k):
    #     print(market)

    assert sqrt_k > 1e13
    net_user_position = MarketPosition(
        market_index,
        market.base_asset_amount,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        PublicKey(0),
        0,
        0,
    )

    current_value = calculate_base_asset_value(market, net_user_position)

    marketNewK = copy.deepcopy(market)
    # marketNewK.amm.peg_multiplier = new_peg
    marketNewK.amm.base_asset_reserve = marketNewK.amm.base_asset_reserve * 1.01
    marketNewK.amm.quote_asset_reserve = marketNewK.amm.quote_asset_reserve * 1.01
    marketNewK.amm.sqrt_k = sqrt_k * 1.01

    net_user_position.quote_asset_amount = current_value

    # print(marketNewK.amm.base_asset_reserve, net_user_position.base_asset_amount)
    # print(net_user_position)
    cost = calculate_position_pnl(marketNewK, net_user_position, False)
    # print(cost)

    old_price = calculate_mark_price(market)
    new_price = calculate_mark_price(marketNewK)
    # print('mark price:', old_price, '->', new_price, '(%.5f pct)' % ((old_price/new_price - 1)*100))

    old_price = calculate_terminal_price(market)
    new_price = calculate_terminal_price(marketNewK)
    # print('terminal price:', old_price, '->', new_price, '(%.5f pct)' % ((old_price/new_price - 1)*100))

    # print('sqrt k:', market.amm.sqrt_k/1e13, '->', marketNewK.amm.sqrt_k/1e13)

    return cost / 1e6, marketNewK


def calculate_repeg_cost(market, new_peg):
    k = int(market.amm.sqrt_k) ** 2
    new_quote_reserves = k / (market.amm.base_asset_reserve + market.base_asset_amount)
    delta_quote_reserves = new_quote_reserves - market.amm.quote_asset_reserve

    cost2 = (
        (delta_quote_reserves
        * (market.amm.peg_multiplier - new_peg))
        / AMM_TIMES_PEG_TO_QUOTE_PRECISION_RATIO
    )

    mark_delta = (
        (market.amm.quote_asset_reserve / market.amm.base_asset_reserve)
        * (new_peg - market.amm.peg_multiplier)
        / PEG_PRECISION
    )

    return cost2 / 1e6, mark_delta


def calculate_k_cost(market, p):
    x = market.amm.base_asset_reserve / 1e13
    y = market.amm.quote_asset_reserve / 1e13
    d = market.base_asset_amount / 1e13
    Q = market.amm.peg_multiplier / 1e3

    cost = -((1 / (x + d) - p / (x * p + d)) * y * d * Q)
    return cost


def calculate_budgeted_k(market, cost):
    C = cost
    x = market.amm.base_asset_reserve / 1e13
    y = market.amm.quote_asset_reserve / 1e13
    d = market.base_asset_amount / 1e13
    Q = market.amm.peg_multiplier / 1e3

    numer = y * d * d * Q - C * d * (x + d)
    denom = C * x * (x + d) + y * d * d * Q
    # print(C, x, y, d, Q)
    # print(numer, denom)
    p = numer / denom
    return p





def calculate_freepeg_cost(market, market_index, target_price, bonus=0):
    mark = calculate_mark_price(market)
    price_div = (mark - target_price) / mark
    # print(price_div)
    p = np.sqrt(mark) / np.sqrt(target_price)
    # p = (1+p)/2
    # print(p)

    bonly, market2 = calculate_curve_op_cost(market, market_index, p, 1 / p)
    print(bonly, p)
    # assert(False)
    pk = 1
    new_peg = market.amm.peg_multiplier
    print('SEE', bonly)
    if bonly < 0:
        print(bonly)
        bonus = 0
        # pk = calculate_budgeted_k(market2, bonly/2)#**(1+price_div)

        new_peg = calculate_budgeted_repeg(market2, bonly) * 1e3
    else:
        pk = calculate_budgeted_k(market2, bonly + bonus)  # **(1+price_div)

    # print(p,':', bonly, p)
    print(new_peg, pk)
    if not pk > 0:
        # print(bonly, bonus, p,1/p)
        print("pk error:", pk)
        return 0, 1, 1, new_peg
        # assert(False)

    # print('------')
    bonly3, market3 = calculate_curve_op_cost(
        market, market_index, pk * p, pk * 1 / p, new_peg
    )
    # konly = calculate_k_cost(market, pk)
    # print(p,':', bonly, pk)

    base_scale = pk * p
    quote_scale = pk * 1 / p

    return bonly3, base_scale, quote_scale, new_peg
