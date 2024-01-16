from typing import Union
from driftpy.types import (
    ExchangeStatus,
    PerpMarketAccount,
    SpotMarketAccount,
    StateAccount,
    is_one_of_variant,
    is_variant,
)


def exchange_paused(state: StateAccount) -> bool:
    return not is_variant(state.exchange_status, "ACTIVE")


def fill_paused(
    state: StateAccount, market: Union[PerpMarketAccount, SpotMarketAccount]
) -> bool:
    return (
        state.exchange_status & ExchangeStatus.FILL_PAUSED
    ) == ExchangeStatus.FILL_PAUSED or is_one_of_variant(
        market.status, ["PAUSED", "FILL_PAUSED"]
    )


def amm_paused(
    state: StateAccount, market: Union[PerpMarketAccount, SpotMarketAccount]
) -> bool:
    return (
        state.exchange_status & ExchangeStatus.AMM_PAUSED
    ) == ExchangeStatus.AMM_PAUSED or is_one_of_variant(
        market.status, ["PAUSED", "AMM_PAUSED"]
    )
