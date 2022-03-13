from driftpy.constants.numeric_constants import (
    # MARK_PRICE_PRECISION,
    PEG_PRECISION,
    AMM_TIMES_PEG_TO_QUOTE_PRECISION_RATIO,
)
from driftpy.types import PositionDirection, AssetType, SwapDirection


def calculate_price(base_asset_amount, quote_asset_amount, peg_multiplier):
    if abs(base_asset_amount) <= 0:
        return 0
    else:
        return (quote_asset_amount / base_asset_amount) * peg_multiplier / PEG_PRECISION


def calculate_terminal_price(market):
    swap_direction = (
        SwapDirection.ADD if market.base_asset_amount > 0 else SwapDirection.REMOVE
    )

    new_base_asset_amount, new_quote_asset_amount = calculate_swap_output(
        market.amm.base_asset_reserve,
        abs(market.base_asset_amount),
        swap_direction,
        market.amm.sqrt_k ** 2,
    )
    # print(new_quote_asset_amount/new_base_asset_amount)

    terminal_price = calculate_price(
        new_base_asset_amount,
        new_quote_asset_amount,
        market.amm.peg_multiplier,
    )

    return terminal_price


def calculate_swap_output(
    input_asset_reserve, swap_amount, swap_direction: SwapDirection, invariant
):
    assert swap_direction in [
        SwapDirection.ADD,
        SwapDirection.REMOVE,
    ], "invalid swap direction parameter"
    assert swap_amount >= 0
    if swap_direction == SwapDirection.ADD:
        new_input_asset_reserve = input_asset_reserve + swap_amount
    else:
        assert input_asset_reserve > swap_amount, "%i > %i" % (
            input_asset_reserve,
            swap_amount,
        )
        new_input_asset_reserve = input_asset_reserve - swap_amount

    new_output_asset_reserve = invariant / new_input_asset_reserve
    return [new_input_asset_reserve, new_output_asset_reserve]


def calculate_amm_reserves_after_swap(
    amm, input_asset_type: AssetType, swap_amount, swap_direction: SwapDirection
):

    if input_asset_type == AssetType.QUOTE:
        swap_amount = (
            swap_amount * AMM_TIMES_PEG_TO_QUOTE_PRECISION_RATIO / amm.peg_multiplier
        )

        # if swap_direction == PositionDirection.SHORT:
        #     swap_amount = swap_amount * (-1)
        [new_quote_asset_reserve, new_base_asset_reserve] = calculate_swap_output(
            amm.quote_asset_reserve,
            swap_amount,
            swap_direction,
            (amm.sqrt_k) ** 2,
        )

    else:
        # swap_amount = swap_amount * PEG_PRECISION
        # if swap_direction == PositionDirection.LONG:
        #     swap_amount = swap_amount * (-1)
        # print(swap_amount, amm)
        [new_base_asset_reserve, new_quote_asset_reserve] = calculate_swap_output(
            amm.base_asset_reserve,
            swap_amount,
            swap_direction,
            (amm.sqrt_k) ** 2,
        )

    return [new_quote_asset_reserve, new_base_asset_reserve]


def get_swap_direction(
    input_asset_type: AssetType, position_direction: PositionDirection
) -> SwapDirection:
    assert input_asset_type in [
        AssetType.BASE,
        AssetType.QUOTE,
    ], "invalid input_asset_type: " + str(input_asset_type)
    assert position_direction in [
        PositionDirection.LONG,
        PositionDirection.SHORT,
    ], "invalid position_direction: " + str(position_direction)
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
