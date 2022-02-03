from driftpy.constants.numeric_constants import MARK_PRICE_PRECISION, PEG_PRECISION
from driftpy.types import PositionDirection
from sumtypes import constructor  # type: ignore


class SwapDirection:
    ADD = constructor()
    REMOVE = constructor()


class AssetType:
    QUOTE = constructor()
    BASE = constructor()


def calculate_price(base_asset_amount, quote_asset_amount, peg_multiplier):
    if abs(base_asset_amount) <= 0:
        return 0
    else:
        return (quote_asset_amount * peg_multiplier / PEG_PRECISION) / base_asset_amount


def calculate_swap_output(
    input_asset_reserve, swap_amount, swap_direction: SwapDirection, invariant
):
    if swap_direction == SwapDirection.ADD:
        new_input_asset_reserve = input_asset_reserve + swap_amount
    else:
        new_input_asset_reserve = input_asset_reserve - swap_amount
    new_output_asset_reserve = invariant / new_input_asset_reserve
    return [new_input_asset_reserve, new_output_asset_reserve]


def calculate_amm_reserves_after_swap(
    amm, input_asset_type: AssetType, swap_amount, swap_direction: SwapDirection
):

    if input_asset_type == AssetType.QUOTE:
        swap_amount = (
            swap_amount
            * MARK_PRICE_PRECISION
            * (PEG_PRECISION ** 2)
            / (amm.peg_multiplier * MARK_PRICE_PRECISION)
        )
        if swap_direction == PositionDirection.SHORT:
            swap_amount = swap_amount * (-1)
        [new_quote_asset_reserve, new_base_asset_reserve] = calculate_swap_output(
            amm.quote_asset_reserve / MARK_PRICE_PRECISION,
            swap_amount,
            swap_direction,
            (amm.sqrt_k / MARK_PRICE_PRECISION) ** 2,
        )

    else:
        swap_amount = swap_amount * PEG_PRECISION
        if swap_direction == PositionDirection.LONG:
            swap_amount = swap_amount * (-1)
        [new_base_asset_reserve, new_quote_asset_reserve] = calculate_swap_output(
            amm.base_asset_reserve / MARK_PRICE_PRECISION,
            swap_amount,
            swap_direction,
            (amm.sqrt_k / MARK_PRICE_PRECISION) ** 2,
        )

    return [new_quote_asset_reserve, new_base_asset_reserve]


def get_swap_direction(
    input_asset_type: AssetType, position_direction: PositionDirection
) -> SwapDirection:
    if (
        position_direction == PositionDirection.LONG
        and input_asset_type == AssetType.BASE
    ):
        return SwapDirection.REMOVE

    if (
        position_direction == PositionDirection.SHORT
        and input_asset_type == AssetType.QUOTE
    ):
        return SwapDirection.REMOVE

    return SwapDirection.ADD


# async def main():
#     # Try out  the functions here

#     # Initiate ClearingHouse
#     drift_acct = await ClearingHouse.create(program)
#     drift_user_acct = await drift_acct.get_user_account()

#     # Get the total value of your collateral
#     balance = drift_user_acct.collateral / 1e6
#     print(f"Total Collateral: {balance}")

#     asset = "SOL"  # Select which asset you want to use here

#     drift_assets = [
#         "SOL",
#         "BTC",
#         "ETH",
#         "LUNA",
#         "AVAX",
#         "BNB",
#         "MATIC",
#         "ATOM",
#         "DOT",
#         "ALGO",
#     ]
#     idx = drift_assets.index(asset)

#     markets = await drift_acct.get_markets_account()
#     market = markets.markets[idx]

#     markets_summary = calculate_market_summary(markets)

#     # Get the predicted funding rates of each market
#     print(calculate_predicted_funding(markets, markets_summary))

#     # Liquidity required to move AMM price of SOL to 95
#     print(calculate_target_price_trade(market, 95, output_asset_type="quote"))

#     # Slippage of a $5000 long trade
#     print(calculate_trade_slippage("LONG", 5000, market, input_asset_type="quote"))


# asyncio.run(main())
