from driftpy.types import OraclePriceData, PerpMarketAccount, PositionDirection


def calculate_bid_price(
    market: PerpMarketAccount, oracle_price_data: OraclePriceData
) -> int:
    from driftpy.math.amm import calculate_updated_amm_spread_reserves, calculate_price

    (
        base_asset_reserve,
        quote_asset_reserve,
        new_peg,
        _,
    ) = calculate_updated_amm_spread_reserves(
        market.amm, PositionDirection.Short(), oracle_price_data
    )

    return calculate_price(base_asset_reserve, quote_asset_reserve, new_peg)


def calculate_ask_price(
    market: PerpMarketAccount, oracle_price_data: OraclePriceData
) -> int:
    from driftpy.math.amm import calculate_updated_amm_spread_reserves, calculate_price

    (
        base_asset_reserve,
        quote_asset_reserve,
        new_peg,
        _,
    ) = calculate_updated_amm_spread_reserves(
        market.amm, PositionDirection.Long(), oracle_price_data
    )

    return calculate_price(base_asset_reserve, quote_asset_reserve, new_peg)
