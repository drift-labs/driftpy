from driftpy.constants.numeric_constants import (
    AMM_RESERVE_PRECISION,
    PRICE_DIV_PEG,
    PEG_PRECISION,
    AMM_TIMES_PEG_TO_QUOTE_PRECISION_RATIO,
    QUOTE_PRECISION,
)
from driftpy.sdk_types import AssetType
from driftpy.types import PositionDirection, SwapDirection, AMM


def calculate_peg_from_target_price(
    target_price: int, base_asset_reserves: int, quote_asset_reserves: int
) -> int:
    return max(
        (
            target_price * base_asset_reserves / quote_asset_reserves
            + (PRICE_DIV_PEG / 2)
        )
        / PRICE_DIV_PEG,
        1,
    )


def calculate_mark_price_amm(amm: AMM):
    return calculate_price(
        amm.base_asset_reserve,
        amm.quote_asset_reserve,
        amm.peg_multiplier,
    )


def calculate_mark_price_amm(amm, oracle_price=None):
    dynamic_peg = "PrePeg" in amm.strategies

    if dynamic_peg:
        peg = calculate_peg_multiplier(amm, oracle_price)
    else:
        peg = amm.peg_multiplier

    return calculate_price(
        amm.base_asset_reserve,
        amm.quote_asset_reserve,
        peg,
    )


def calculate_bid_price_amm(amm: AMM, oracle_price=None):
    base_asset_reserves, quote_asset_reserves = calculate_spread_reserves(
        amm, PositionDirection.SHORT, oracle_price=oracle_price
    )
    return calculate_price(
        base_asset_reserves, quote_asset_reserves, amm.peg_multiplier
    )


def calculate_ask_price_amm(amm: AMM, oracle_price=None):
    base_asset_reserves, quote_asset_reserves = calculate_spread_reserves(
        amm, PositionDirection.LONG, oracle_price=oracle_price
    )
    return calculate_price(
        base_asset_reserves, quote_asset_reserves, amm.peg_multiplier
    )


def calculate_price(base_asset_amount, quote_asset_amount, peg_multiplier):
    if abs(base_asset_amount) <= 0:
        return 0
    else:
        return (quote_asset_amount / base_asset_amount) * peg_multiplier / PEG_PRECISION


def calculate_terminal_price(market):
    swap_direction = (
        SwapDirection.ADD if market.base_asset_amount > 0 else SwapDirection.REMOVE
    )

    new_quote_asset_amount, new_base_asset_amount = calculate_swap_output(
        abs(market.base_asset_amount),
        market.amm.base_asset_reserve,
        swap_direction,
        market.amm.sqrt_k,
    )
    # print(new_quote_asset_amount/new_base_asset_amount)

    terminal_price = calculate_price(
        new_base_asset_amount,
        new_quote_asset_amount,
        market.amm.peg_multiplier,
    )

    return terminal_price


def calculate_swap_output(
    swap_amount, input_asset_reserve, swap_direction: SwapDirection, invariant_sqrt
):
    invariant = invariant_sqrt * invariant_sqrt
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
    return [new_output_asset_reserve, new_input_asset_reserve]


def calculate_amm_reserves_after_swap(
    amm,
    input_asset_type: AssetType,
    swap_amount,
    swap_direction: SwapDirection,
):
    if input_asset_type == AssetType.QUOTE:
        swap_amount = (
            swap_amount * AMM_TIMES_PEG_TO_QUOTE_PRECISION_RATIO / amm.peg_multiplier
        )

        [new_base_asset_reserve, new_quote_asset_reserve] = calculate_swap_output(
            swap_amount,
            amm.quote_asset_reserve,
            swap_direction,
            amm.sqrt_k,
        )
    else:
        [new_quote_asset_reserve, new_base_asset_reserve] = calculate_swap_output(
            swap_amount,
            amm.base_asset_reserve,
            swap_direction,
            amm.sqrt_k,
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


def calculate_budgeted_repeg(amm, cost, target_px=None, pay_only=False):

    if target_px == None:
        target_px = amm.last_oracle_price  # / 1e10
        assert amm.last_oracle_price != 0

    C = cost
    x = amm.base_asset_reserve / AMM_RESERVE_PRECISION
    y = amm.quote_asset_reserve / AMM_RESERVE_PRECISION
    d = amm.base_asset_amount_with_amm / AMM_RESERVE_PRECISION
    Q = amm.peg_multiplier / PEG_PRECISION
    k = (amm.sqrt_k / AMM_RESERVE_PRECISION) ** 2

    dqar = y - (k / (x + d))

    # print('dqar', dqar)
    cur_px = y / x * Q
    target_peg = target_px * x / y

    peg_change_direction = target_peg - Q

    use_target_peg = (dqar < 0 and peg_change_direction > 0) or (
        dqar > 0 and peg_change_direction < 0
    )

    if dqar != 0 and not use_target_peg:
        new_peg = Q + (C / dqar)
    else:
        new_peg = target_peg

    # print(cur_px, target_px, Q, '->', new_peg, '||', target_peg, '(budget:', C,')', d, dqar)
    if cur_px > target_px and new_peg < target_peg:
        new_peg = target_peg
    if cur_px < target_px and new_peg > target_peg:
        new_peg = target_peg

    if pay_only:
        if new_peg < Q and d > 0:
            new_peg = Q
        if new_peg > Q and d < 0:
            new_peg = Q

    # print("new_peg", new_peg, target_peg)
    return new_peg


def calculate_peg_multiplier(
    amm, oracle_price=None, now=None, delay=None, budget_cost=None
):
    # todo: make amm have all the vars needed
    if "PrePeg" in amm.strategies:
        if oracle_price is None:
            oracle_price = amm.last_oracle_price
            if delay is None:
                if now is not None:
                    delay = now - amm.last_oracle_price_twap_ts
                else:
                    delay = 100
            # delay_discount = 1/(delay*delay/2)
            # last_mark = calculate_mark_price_amm(market.amm)
            # target_px = last_mark + ((oracle_price-last_mark)*delay_discount)
            target_px = oracle_price
        else:
            target_px = oracle_price

        if budget_cost is None:
            fee_pool = (amm.total_fee_minus_distributions / QUOTE_PRECISION) - (
                amm.total_fee / QUOTE_PRECISION
            ) / 2
            budget_cost = max(0, fee_pool)
            # print('budget to repeg:', budget_cost, 'to target_price', target_px)

        new_peg = int(
            calculate_budgeted_repeg(amm, budget_cost, target_px=target_px)
            * PEG_PRECISION
        )
        return new_peg
    elif "PreFreePeg" in amm.strategies:
        target_px = oracle_price

        if budget_cost is None:
            fee_pool = (amm.total_fee_minus_distributions / QUOTE_PRECISION) - (
                amm.total_fee / QUOTE_PRECISION
            ) / 2
            budget_cost = max(0, fee_pool)

        new_peg = int(
            calculate_budgeted_repeg(amm, budget_cost, target_px=target_px)
            * PEG_PRECISION
        )
        return new_peg
    else:
        return amm.peg_multiplier


def calculate_spread_reserves(
    amm, position_direction: PositionDirection, oracle_price=None
):
    BID_ASK_SPREAD_PRECISION = 1_000_000  # this is 100% (thus 1_000 = .1%)
    mark_price = calculate_mark_price_amm(amm, oracle_price=oracle_price)
    spread = amm.base_spread
    # print('sprad reserve calc:', mark_price, spread, oracle_price)

    if "OracleRetreat" in amm.strategies:
        if oracle_price is None:
            oracle_price = amm.last_oracle_price
        pct_delta = float(oracle_price - mark_price) / mark_price
        # print(amm.last_oracle_price, mark_price, pct_delta, spread)
        if (pct_delta > 0 and position_direction == PositionDirection.LONG) or (
            pct_delta < 0 and position_direction == PositionDirection.SHORT
        ):
            oracle_spread = abs(pct_delta) * QUOTE_PRECISION * 2
            if oracle_spread > spread:
                spread = oracle_spread * 2
        else:
            # no retreat
            pass

    if "VolatilityScale" in amm.strategies:
        spread *= min(2, max(1, amm.mark_std))

    if "InventorySkew" in amm.strategies:
        max_scale = 5  # if 'OracleRetreat' not in amm.strategies else 20

        effective_position = (
            amm.base_asset_amount_with_amm
        )  # (amm.sqrt_k - amm.base_asset_reserve)

        net_cost_basis = (
            amm.quote_asset_amount_long - (amm.quote_asset_amount_short)
        ) / QUOTE_PRECISION
        net_base_asset_value = (
            (amm.quote_asset_reserve - amm.terminal_quote_asset_reserve)
            / AMM_RESERVE_PRECISION
            * amm.peg_multiplier
            / PEG_PRECISION
        )
        local_base_asset_value = mark_price * (
            effective_position / AMM_RESERVE_PRECISION
        )

        local_pnl = local_base_asset_value - net_cost_basis
        net_pnl = net_base_asset_value - net_cost_basis
        # print("local pnl: ", local_pnl, "net pnl:", net_pnl)
        if amm.total_fee_minus_distributions > 0:
            effective_leverage = (local_pnl - net_pnl) / (
                amm.total_fee_minus_distributions / QUOTE_PRECISION
            )
            print("effective_leverage:", effective_leverage)
            if position_direction == PositionDirection.LONG:
                # print((1 + (effective_position/(amm.sqrt_k/10000))))
                spread *= min(max_scale, max(1, (1 + effective_leverage)))
            else:
                spread *= min(max_scale, max(1, (1 - effective_leverage)))
        else:
            spread *= max_scale

    amm.last_spread = spread

    quote_asset_reserve_delta = 0
    if spread > 0:
        quote_asset_reserve_delta = amm.quote_asset_reserve / (
            BID_ASK_SPREAD_PRECISION / (spread / 4)
        )
    # print(quote_asset_reserve_delta)

    if position_direction == PositionDirection.LONG:
        quote_asset_reserve = amm.quote_asset_reserve + quote_asset_reserve_delta
    else:
        quote_asset_reserve = amm.quote_asset_reserve - quote_asset_reserve_delta

    base_asset_reserve = (amm.sqrt_k * amm.sqrt_k) / quote_asset_reserve
    # print(base_asset_reserve, quote_asset_reserve, amm.sqrt_k)
    return base_asset_reserve, quote_asset_reserve


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
