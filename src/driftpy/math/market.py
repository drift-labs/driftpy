from driftpy.math.amm import calculate_price, calculate_spread_reserves, calculate_peg_multiplier
from driftpy.types import PositionDirection, AssetType, SwapDirection
import copy

def calculate_mark_price(market, oracle_price=None):
    dynamic_peg = 'PrePeg' in market.amm.strategies

    if dynamic_peg:
        peg = calculate_peg_multiplier(market.amm, oracle_price)
    else:
        peg = market.amm.peg_multiplier

    return calculate_price(
        market.amm.base_asset_reserve,
        market.amm.quote_asset_reserve,
        peg,
    )


def calculate_bid_price(market, oracle_price=None):
    dynamic_peg = 'PrePeg' in market.amm.strategies

    if dynamic_peg:
        peg = calculate_peg_multiplier(market.amm, oracle_price)
    else:
        peg = market.amm.peg_multiplier

    candidate_amm = copy.deepcopy(market.amm)
    candidate_amm.peg_multiplier = peg

    base_asset_reserves, quote_asset_reserves = calculate_spread_reserves(
        candidate_amm, PositionDirection.SHORT,
        oracle_price=oracle_price
    )

    return calculate_price(
        base_asset_reserves, quote_asset_reserves, peg
    )


def calculate_ask_price(market, oracle_price=None):
    dynamic_peg = 'PrePeg' in market.amm.strategies

    if dynamic_peg:
        peg = calculate_peg_multiplier(market.amm, oracle_price)
    else:
        peg = market.amm.peg_multiplier

    candidate_amm = copy.deepcopy(market.amm)
    candidate_amm.peg_multiplier = peg

    base_asset_reserves, quote_asset_reserves = calculate_spread_reserves(
        candidate_amm, PositionDirection.LONG,
        oracle_price=oracle_price
    )

    return calculate_price(
        base_asset_reserves, quote_asset_reserves, peg
    )
