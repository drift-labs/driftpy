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
    return not is_variant(state.exchange_status, "Active")


def fill_paused(
    state: StateAccount, market: Union[PerpMarketAccount, SpotMarketAccount]
) -> bool:
    return (
        state.exchange_status & ExchangeStatus.FillPaused
    ) == ExchangeStatus.FillPaused or is_one_of_variant(
        market.status, ["Paused", "FillPaused"]
    )


def amm_paused(
    state: StateAccount, market: Union[PerpMarketAccount, SpotMarketAccount]
) -> bool:
    return (
        state.exchange_status & ExchangeStatus.AmmPaused
    ) == ExchangeStatus.AmmPaused or is_one_of_variant(
        market.status, ["Paused", "AmmPaused"]
    )
