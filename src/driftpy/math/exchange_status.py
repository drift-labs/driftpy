from typing import Union
from driftpy.types import (
    PerpMarketAccount,
    SpotMarketAccount,
    StateAccount,
    is_one_of_variant,
    is_variant,
)


class ExchangeStatusValues:
    Active = 1
    DepositPaused = 2
    WithdrawPaused = 4
    AmmPaused = 8
    FillPaused = 16
    LiqPaused = 32
    FundingPaused = 64
    SettlePnlPaused = 128


def exchange_paused(state: StateAccount) -> bool:
    return not is_variant(state.exchange_status, "Active")


def fill_paused(
    state: StateAccount, market: Union[PerpMarketAccount, SpotMarketAccount]
) -> bool:
    return (
        state.exchange_status & ExchangeStatusValues.FillPaused
    ) == ExchangeStatusValues.FillPaused or is_one_of_variant(
        market.status, ["Paused", "FillPaused"]
    )


def amm_paused(
    state: StateAccount, market: Union[PerpMarketAccount, SpotMarketAccount]
) -> bool:
    return (
        state.exchange_status & ExchangeStatusValues.AmmPaused
    ) == ExchangeStatusValues.AmmPaused or is_one_of_variant(
        market.status, ["Paused", "AmmPaused"]
    )
