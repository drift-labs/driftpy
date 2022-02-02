from anchorpy import Idl, Program, Provider
from solana.publickey import PublicKey
import json
import time
import os
from pathlib import Path
from driftpy.clearing_house import ClearingHouse
import asyncio
import sys
from driftpy.constants.markets import MARKETS
from driftpy.constants.numeric_constants import (
    MARK_PRICE_PRECISION,
    FUNDING_PRECISION,
    PEG_PRECISION,
    AMM_TO_QUOTE_PRECISION_RATIO,
)
from datetime import datetime, timedelta
import pandas as pd
import math


def calculateMarketSummary(markets):

    markets_summary = pd.concat(
        [
            pd.DataFrame(MARKETS).iloc[:, :3],
            pd.DataFrame(markets.markets),
            pd.DataFrame([x.amm for x in markets.markets]),
        ],
        axis=1,
    ).dropna(subset=["symbol"])
    return markets_summary


""""""


def calculatePredictedFunding(markets, markets_summary):

    last_funding_ts = pd.to_datetime(markets.markets[0].amm.last_funding_rate_ts * 1e9)
    next_funding_ts = last_funding_ts + timedelta(hours=1)
    next_funding_ts

    summary = {}
    hours_in_day = 24
    summary["next_funding_rate"] = (
        (
            markets_summary["last_mark_price_twap"]
            - markets_summary["last_oracle_price_twap"]
        )
        / markets_summary["last_oracle_price_twap"]
        / hours_in_day
    )

    summary["mark_price"] = (
        (markets_summary["quote_asset_reserve"] / markets_summary["base_asset_reserve"])
        * markets_summary["peg_multiplier"]
        / PEG_PRECISION
    )

    return pd.concat([pd.DataFrame(MARKETS).iloc[:, :3], pd.DataFrame(summary)], axis=1)


""""""


def calculatePrice(baseAssetAmount, quoteAssetAmount, peg_multiplier):
    if abs(baseAssetAmount) <= 0:
        return 0
    else:
        return (quoteAssetAmount * peg_multiplier / PEG_PRECISION) / baseAssetAmount


""""""


def calculateMarkPrice(market):
    return calculatePrice(
        market.amm.base_asset_reserve,
        market.amm.quote_asset_reserve,
        market.amm.peg_multiplier,
    )


""""""


def calculateTargetPriceTrade(
    markets, symbol: str, targetPrice: float, outputAssetType=None
):

    idx = driftAssets.index(symbol)
    market = markets.markets[idx]
    markPriceBefore = calculateMarkPrice(market)

    if targetPrice > markPriceBefore:
        priceGap = targetPrice - markPriceBefore
        targetPrice = markPriceBefore + priceGap
    else:
        priceGap = markPriceBefore - targetPrice
        targetPrice = markPriceBefore - priceGap

    baseAssetReserveBefore = (
        markets.markets[idx].amm.base_asset_reserve / MARK_PRICE_PRECISION
    )
    quoteAssetReserveBefore = (
        markets.markets[idx].amm.quote_asset_reserve / MARK_PRICE_PRECISION
    )
    peg = markets.markets[idx].amm.peg_multiplier / MARK_PRICE_PRECISION
    invariant = (markets.markets[idx].amm.sqrt_k / MARK_PRICE_PRECISION) ** 2
    k = invariant * MARK_PRICE_PRECISION
    bias_modifier = 1

    if markPriceBefore > targetPrice:
        baseAssetReserveAfter = (
            math.sqrt((k / targetPrice) * (peg / PEG_PRECISION) - bias_modifier) - 1
        )
        quoteAssetReserveAfter = (k / MARK_PRICE_PRECISION) / baseAssetReserveAfter

        direction = "SHORT"
        tradeSize = (
            (quoteAssetReserveBefore - quoteAssetReserveAfter) * (peg / PEG_PRECISION)
        ) / AMM_TO_QUOTE_PRECISION_RATIO
        baseSize = baseAssetReserveAfter - baseAssetReserveBefore

    elif markPriceBefore < targetPrice:
        baseAssetReserveAfter = (
            math.sqrt((k / targetPrice) * (peg / PEG_PRECISION) + bias_modifier) + 1
        )
        quoteAssetReserveAfter = (k / MARK_PRICE_PRECISION) / baseAssetReserveAfter

        direction = "LONG"
        tradeSize = (
            (quoteAssetReserveAfter - quoteAssetReserveBefore) * (peg / PEG_PRECISION)
        ) / AMM_TO_QUOTE_PRECISION_RATIO
        baseSize = baseAssetReserveBefore - baseAssetReserveAfter

    else:
        # no trade, market is at target
        direction = "LONG"
        tradeSize = 0
        return [direction, tradeSize, targetPrice, targetPrice]

    entryPrice = (
        tradeSize * AMM_TO_QUOTE_PRECISION_RATIO * MARK_PRICE_PRECISION / abs(baseSize)
    )

    if outputAssetType == "quote":
        return [direction, tradeSize * 10 ** 14, entryPrice, targetPrice]
    else:
        return [direction, baseSize / 1000, entryPrice, targetPrice]


""""""


def calculateSwapOutput(inputAssetReserve, swapAmount, swapDirection, invariant):
    if swapDirection == "LONG":
        newInputAssetReserve = inputAssetReserve + swapAmount
    else:
        newInputAssetReserve = inputAssetReserve - swapAmount
    newOutputAssetReserve = invariant / newInputAssetReserve
    return [newInputAssetReserve, newOutputAssetReserve]


""""""


def calculateAmmReservesAfterSwap(amm, inputAssetType, swapAmount, swapDirection):
    assert swapAmount >= 0

    if inputAssetType == "quote":
        swapAmount = swapAmount

        [newQuoteAssetReserve, newBaseAssetReserve] = calculateSwapOutput(
            amm.quote_asset_reserve / MARK_PRICE_PRECISION,
            swapAmount,
            swapDirection,
            (amm.sqrt_k / MARK_PRICE_PRECISION) ** 2,
        )

    else:
        [newBaseAssetReserve, newQuoteAssetReserve] = calculateSwapOutput(
            amm.base_asset_reserve / MARK_PRICE_PRECISION,
            swapAmount,
            swapDirection,
            (amm.sqrt_k / MARK_PRICE_PRECISION) ** 2,
        )

    return [newQuoteAssetReserve, newBaseAssetReserve]


""""""


def calculateTradeAcquiredAmounts(direction, amount, market, inputAssetType="quote"):
    if amount == 0:
        return [0, 0]
    [newQuoteAssetReserve, newBaseAssetReserve] = calculateAmmReservesAfterSwap(
        market.amm, inputAssetType, amount, direction
    )

    acquiredBase = (
        market.amm.base_asset_reserve / MARK_PRICE_PRECISION - newBaseAssetReserve
    )
    acquireQuote = (
        market.amm.quote_asset_reserve / MARK_PRICE_PRECISION - newQuoteAssetReserve
    )

    return [acquiredBase, acquireQuote]


""""""


def calculateTradeSlippage(direction, amount, markets, symbol, inputAssetType="quote"):

    idx = driftAssets.index(symbol)
    market = markets.markets[idx]

    oldPrice = calculateMarkPrice(market)
    if amount == 0:
        return [0, 0, oldPrice, oldPrice]

    [acquiredBase, acquiredQuote] = calculateTradeAcquiredAmounts(
        direction, amount, market, inputAssetType
    )

    entryPrice = (
        calculatePrice(
            acquiredBase,
            acquiredQuote,
            market.amm.peg_multiplier * (-1) / MARK_PRICE_PRECISION,
        )
        * MARK_PRICE_PRECISION
    )

    newPrice = (
        calculatePrice(
            market.amm.base_asset_reserve / MARK_PRICE_PRECISION - acquiredBase,
            market.amm.quote_asset_reserve / MARK_PRICE_PRECISION - acquiredQuote,
            market.amm.peg_multiplier / MARK_PRICE_PRECISION,
        )
        * MARK_PRICE_PRECISION
    )

    if direction == "SHORT":
        assert newPrice < oldPrice
    else:
        assert oldPrice < newPrice

    pctMaxSlippage = abs((newPrice - oldPrice) / oldPrice)
    pctAvgSlippage = abs((entryPrice - oldPrice) / oldPrice)

    return [pctAvgSlippage, pctMaxSlippage, entryPrice, newPrice]
