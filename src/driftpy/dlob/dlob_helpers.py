from typing import Dict, Union
from driftpy.types import (
    MarketType,
    PerpMarketAccount,
    SpotMarketAccount,
    StateAccount,
    is_variant,
)


def get_maker_rebate(
    market_type: MarketType,
    state_account: StateAccount,
    market_account: Union[PerpMarketAccount, SpotMarketAccount],
):
    if is_variant(market_type, "Perp"):
        maker_rebate_numerator = state_account.perp_fee_structure.fee_tiers[
            0
        ].maker_rebate_numerator
        maker_rebate_denominator = state_account.perp_fee_structure.fee_tiers[
            0
        ].maker_rebate_denominator
    else:
        maker_rebate_numerator = state_account.spot_fee_structure.fee_tiers[
            0
        ].maker_rebate_numerator
        maker_rebate_denominator = state_account.spot_fee_structure.fee_tiers[
            0
        ].maker_rebate_denominator

    fee_adjustment = (
        market_account.fee_adjustment
        if market_account.fee_adjustment is not None
        else 0
    )
    if fee_adjustment != 0:
        maker_rebate_numerator += (maker_rebate_numerator * fee_adjustment) // 100

    return maker_rebate_numerator, maker_rebate_denominator


def get_node_lists(order_lists):
    from driftpy.dlob.dlob_node import MarketNodeLists

    order_lists: Dict[str, Dict[int, MarketNodeLists]]

    for _, node_lists in order_lists.get("perp", {}).items():
        yield node_lists.resting_limit["bid"]
        yield node_lists.resting_limit["ask"]
        yield node_lists.taking_limit["bid"]
        yield node_lists.taking_limit["ask"]
        yield node_lists.market["bid"]
        yield node_lists.market["ask"]
        yield node_lists.floating_limit["bid"]
        yield node_lists.floating_limit["ask"]
        yield node_lists.trigger["above"]
        yield node_lists.trigger["below"]

    for _, node_lists in order_lists.get("spot", {}).items():
        yield node_lists.resting_limit["bid"]
        yield node_lists.resting_limit["ask"]
        yield node_lists.taking_limit["bid"]
        yield node_lists.taking_limit["ask"]
        yield node_lists.market["bid"]
        yield node_lists.market["ask"]
        yield node_lists.floating_limit["bid"]
        yield node_lists.floating_limit["ask"]
        yield node_lists.trigger["above"]
        yield node_lists.trigger["below"]
