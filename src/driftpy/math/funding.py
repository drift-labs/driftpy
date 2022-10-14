from driftpy.types import (
    PerpMarket,
)

from driftpy.constants.numeric_constants import (
    PRICE_PRECISION as PRICE_PRECISION,
    # PEG_PRECISION,
    AMM_RESERVE_PRECISION,
    QUOTE_PRECISION,
    # FUNDING_PRECISION,
    # PRICE_TO_QUOTE_PRECISION,
    # AMM_TO_QUOTE_PRECISION_RATIO,
    # AMM_TIMES_PEG_TO_QUOTE_PRECISION_RATIO,
)


def calculate_long_short_funding(market: PerpMarket):
    sym = calculate_symmetric_funding(market)
    capped = calculate_capped_funding(market)
    if market.base_asset_amount > 0:
        return [capped, sym]
    elif market.base_asset_amount < 0:
        return [sym, capped]
    else:
        return [sym, sym]


def calculate_capped_funding(market: PerpMarket):

    smaller_side = min(
        abs(market.amm.base_asset_amount_short), market.amm.base_asset_amount_long
    )
    larger_side = max(
        abs(market.amm.base_asset_amount_short), market.amm.base_asset_amount_long
    )

    next_funding = calculate_oracle_mark_spread_owed(market)
    funding_fee_pool = calculate_funding_fee_pool(market)

    if larger_side != 0:
        capped_funding = (
            smaller_side * next_funding
            + funding_fee_pool * PRICE_PRECISION * AMM_RESERVE_PRECISION
        ) / larger_side
    else:
        capped_funding = next_funding
    # estimated capped amount above estimated next amount, then not a cap
    if abs(capped_funding) >= abs(next_funding):
        capped_funding = next_funding

    capped_funding /= market.amm.last_oracle_price_twap * 100

    return capped_funding


def calculate_symmetric_funding(market: PerpMarket):
    next_funding = calculate_oracle_mark_spread_owed(market)

    next_funding /= market.amm.last_oracle_price_twap * 100

    return next_funding


def calculate_oracle_mark_spread_owed(market: PerpMarket):
    return (market.amm.last_mark_price_twap - market.amm.last_oracle_price_twap) / 24


def calculate_funding_fee_pool(market: PerpMarket):
    fee_pool = (
        market.amm.total_fee_minus_distributions - market.amm.total_fee / 2
    ) / QUOTE_PRECISION
    funding_interval_fee_pool = fee_pool * 2 / 3
    return funding_interval_fee_pool
