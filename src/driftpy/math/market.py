from driftpy.math.amm import calculate_price, calculate_spread_reserves
from driftpy.types import PositionDirection, AssetType, SwapDirection


def calculate_mark_price(market):
    return calculate_price(
        market.amm.base_asset_reserve,
        market.amm.quote_asset_reserve,
        market.amm.peg_multiplier,
    )


def calculate_bid_price(market, oracle_price=None):
    base_asset_reserves, quote_asset_reserves = calculate_spread_reserves(
        market.amm, PositionDirection.SHORT,
        oracle_price=oracle_price
    )
    return calculate_price(
        base_asset_reserves, quote_asset_reserves, market.amm.peg_multiplier
    )


def calculate_ask_price(market, oracle_price=None):
    base_asset_reserves, quote_asset_reserves = calculate_spread_reserves(
        market.amm, PositionDirection.LONG,
        oracle_price=oracle_price
    )
    return calculate_price(
        base_asset_reserves, quote_asset_reserves, market.amm.peg_multiplier
    )
