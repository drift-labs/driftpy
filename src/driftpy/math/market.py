from driftpy.math.amm import calculate_price


def calculate_mark_price(market):
    return calculate_price(
        market.amm.base_asset_reserve,
        market.amm.quote_asset_reserve,
        market.amm.peg_multiplier,
    )
