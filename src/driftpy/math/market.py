from driftpy.math.amm import calculate_price, calculate_spread_reserves, calculate_peg_multiplier, calculate_terminal_price, calculate_budgeted_repeg
from driftpy.types import PositionDirection, AssetType, SwapDirection, MarketPosition
import copy
from solana.publickey import PublicKey
import numpy as np
from driftpy.math.positions import calculate_base_asset_value, calculate_position_pnl

def calculate_freepeg_cost(market, target_price, bonus=0):

    def calculate_budgeted_k(market, cost):
        if cost == 0:
            return 1

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

    def calculate_curve_op_cost(market, base_p, quote_p, new_peg=None):
        #     print(market)
        # print(base_p, quote_p)
        if not (base_p > 0 and quote_p > 0):
            print(base_p, quote_p)
            assert False
        net_user_position = MarketPosition(
            market.market_index,
            market.amm.net_base_asset_amount,
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

    mark = calculate_mark_price(market)
    # price_div = (mark - target_price) / mark
    p = np.sqrt(mark) / np.sqrt(target_price)

    bonly, market2 = calculate_curve_op_cost(market, p, 1 / p)
    # print(bonly, p)
    # assert(False)
    pk = 1
    new_peg = market.amm.peg_multiplier

    if bonly < 0:
        print(bonly)
        bonus = 0
        # pk = calculate_budgeted_k(market2, bonly/2)#**(1+price_div)

        new_peg = calculate_budgeted_repeg(market2.amm, bonly, target_price) * 1e3
    else:
        pk = calculate_budgeted_k(market2, bonly + bonus)  # **(1+price_div)

    # print(p,':', bonly, p)
    # print(new_peg, pk)
    if not pk > 0:
        # print(bonly, bonus, p,1/p)
        print("pk error:", pk)
        return 0, 1, 1, new_peg
        # assert(False)

    # print('------')
    bonly3, market3 = calculate_curve_op_cost(
        market, pk * p, pk * 1 / p, new_peg
    )
    # konly = calculate_k_cost(market, pk)
    # print(p,':', bonly, pk)

    base_scale = pk * p
    quote_scale = pk * 1 / p

    return bonly3, base_scale, quote_scale, new_peg



def calculate_candidate_amm(market, oracle_price=None):
    prepeg = 'PrePeg' in market.amm.strategies
    prefreepeg = 'PreFreePeg' in market.amm.strategies

    base_scale = 1
    quote_scale = 1

    if prepeg:
        peg = calculate_peg_multiplier(market.amm, oracle_price)
    elif prefreepeg:
        freepeg_cost, base_scale, quote_scale, peg = calculate_freepeg_cost(market, oracle_price)
        # print(freepeg_cost, 'is cost to freepeg')
    else:
        peg = market.amm.peg_multiplier

    candidate_amm = copy.deepcopy(market.amm)
    candidate_amm.base_asset_reserve *= base_scale
    candidate_amm.quote_asset_reserve *= quote_scale
    candidate_amm.peg_multiplier = peg
    return candidate_amm

def calculate_long_short_reserves_and_peg(market, oracle_price=None):
    candidate_amm = calculate_candidate_amm(market, oracle_price)

    base_asset_reserves_short, quote_asset_reserves_short = calculate_spread_reserves(
        candidate_amm, PositionDirection.SHORT,
        oracle_price=oracle_price
    )

    base_asset_reserves_long, quote_asset_reserves_long = calculate_spread_reserves(
        candidate_amm, PositionDirection.LONG,
        oracle_price=oracle_price
    )

    return [
            base_asset_reserves_long, quote_asset_reserves_long, 
            base_asset_reserves_short, quote_asset_reserves_short,
            candidate_amm.peg_multiplier
    ]


def calculate_mark_price(market, oracle_price=None):
    if oracle_price is not None:
        candidate_amm = calculate_candidate_amm(market, oracle_price)
    else:
        candidate_amm = market.amm

    return calculate_price(
        candidate_amm.base_asset_reserve, candidate_amm.quote_asset_reserve, candidate_amm.peg_multiplier
    )

def calculate_bid_ask_price(market, oracle_price=None):
    [base_asset_reserves_long, quote_asset_reserves_long, 
            base_asset_reserves_short, quote_asset_reserves_short,
            peg_multiplier] = calculate_long_short_reserves_and_peg(market, oracle_price)

    bid_price = calculate_price(
        base_asset_reserves_short, quote_asset_reserves_short, peg_multiplier
    )

    ask_price = calculate_price(
        base_asset_reserves_long, quote_asset_reserves_long, peg_multiplier
    )

    return bid_price, ask_price

def calculate_bid_price(market, oracle_price=None):
    candidate_amm = calculate_candidate_amm(market, oracle_price)

    base_asset_reserves_short, quote_asset_reserves_short = calculate_spread_reserves(
        candidate_amm, PositionDirection.SHORT,
        oracle_price=oracle_price
    )

    return calculate_price(
        base_asset_reserves_short, quote_asset_reserves_short, candidate_amm.peg_multiplier
    )


def calculate_ask_price(market, oracle_price=None):
    candidate_amm = calculate_candidate_amm(market, oracle_price)

    base_asset_reserves_long, quote_asset_reserves_long = calculate_spread_reserves(
        candidate_amm, PositionDirection.LONG,
        oracle_price=oracle_price
    )

    return calculate_price(
        base_asset_reserves_long, quote_asset_reserves_long, candidate_amm.peg_multiplier
    )
