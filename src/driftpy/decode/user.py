from typing import List, Literal

from solders.pubkey import Pubkey

from driftpy.types import (
    MarginMode,
    MarketType,
    Order,
    OrderStatus,
    OrderTriggerCondition,
    OrderType,
    PerpPosition,
    PositionDirection,
    SpotBalanceType,
    SpotPosition,
    UserAccount,
)

# Faster decoding for User Accounts
# We skip all zero data to streamline the process and avoid unnecessary decoding


def read_uint8(buffer, offset):
    return buffer[offset]


def read_uint16_le(buffer, offset):
    return int.from_bytes(buffer[offset : offset + 2], byteorder="little")


def read_int32_le(buffer, offset, signed):
    return int.from_bytes(
        buffer[offset : offset + 4], byteorder="little", signed=signed
    )


def read_bigint64le(buffer, offset: Literal, signed: bool):
    byte_slice = buffer[offset : offset + 8]

    return int.from_bytes(byte_slice, byteorder="little", signed=signed)


def decode_user(buffer: bytes) -> UserAccount:
    offset = 8
    authority = Pubkey(buffer[offset : offset + 32])
    offset += 32
    delegate = Pubkey(buffer[offset : offset + 32])
    offset += 32
    name = [buffer[offset + i] for i in range(32)]
    offset += 32

    spot_positions: List[SpotPosition] = []
    for _ in range(8):
        scaled_balance = read_bigint64le(buffer, offset, False)
        open_orders = buffer[offset + 35]
        if scaled_balance == 0 and open_orders == 0:
            offset += 40
            continue

        offset += 8
        open_bids = read_bigint64le(buffer, offset, True)
        offset += 8
        open_asks = read_bigint64le(buffer, offset, True)
        offset += 8
        cumulative_deposits = read_bigint64le(buffer, offset, True)
        offset += 8
        market_index = read_uint16_le(buffer, offset)
        offset += 2
        balance_type_num = read_uint8(buffer, offset)
        balance_type = (
            SpotBalanceType.Deposit()
            if balance_type_num == 0
            else SpotBalanceType.Borrow()
        )
        offset += 6
        spot_positions.append(
            SpotPosition(
                scaled_balance,
                open_bids,
                open_asks,
                cumulative_deposits,
                market_index,
                balance_type,
                open_orders,
                [0, 0, 0, 0],
            )
        )

    perp_positions: List[PerpPosition] = []
    for _ in range(8):
        base_asset_amount = read_bigint64le(buffer, offset + 8, True)
        quote_asset_amount = read_bigint64le(buffer, offset + 16, True)
        lp_shares = read_bigint64le(buffer, offset + 64, False)
        open_orders = buffer[offset + 94]

        if (
            base_asset_amount == 0
            and open_orders == 0
            and quote_asset_amount == 0
            and lp_shares == 0
        ):
            offset += 96
            continue

        last_cumulative_funding_rate = read_bigint64le(buffer, offset, True)
        offset += 24
        quote_break_even_amount = read_bigint64le(buffer, offset, True)
        offset += 8
        quote_entry_amount = read_bigint64le(buffer, offset, True)
        offset += 8
        open_bids = read_bigint64le(buffer, offset, True)
        offset += 8
        open_asks = read_bigint64le(buffer, offset, True)
        offset += 8
        settled_pnl = read_bigint64le(buffer, offset, True)
        offset += 16
        last_base_asset_amount_per_lp = read_bigint64le(buffer, offset, True)
        offset += 8
        last_quote_asset_amount_per_lp = read_bigint64le(buffer, offset, True)
        offset += 8
        remainder_base_asset_amount = read_int32_le(buffer, offset, True)
        offset += 4
        market_index = read_uint16_le(buffer, offset)
        offset += 3
        per_lp_base = read_uint8(buffer, offset)
        offset += 1

        perp_positions.append(
            PerpPosition(
                last_cumulative_funding_rate,
                base_asset_amount,
                quote_asset_amount,
                quote_break_even_amount,
                quote_entry_amount,
                open_bids,
                open_asks,
                settled_pnl,
                lp_shares,
                last_base_asset_amount_per_lp,
                last_quote_asset_amount_per_lp,
                remainder_base_asset_amount,
                market_index,
                open_orders,
                per_lp_base,
            )
        )

    orders: List[Order] = []
    for _ in range(32):
        # skip order if it's not open
        if read_uint8(buffer, offset + 82) != 1:
            offset += 96
            continue

        slot = read_bigint64le(buffer, offset, False)
        offset += 8

        price = read_bigint64le(buffer, offset, False)
        offset += 8

        base_asset_amount = read_bigint64le(buffer, offset, False)
        offset += 8

        base_asset_amount_filled = read_bigint64le(buffer, offset, False)
        offset += 8

        quote_asset_amount_filled = read_bigint64le(buffer, offset, False)
        offset += 8

        trigger_price = read_bigint64le(buffer, offset, False)
        offset += 8

        auction_start_price = read_bigint64le(buffer, offset, True)
        offset += 8

        auction_end_price = read_bigint64le(buffer, offset, True)
        offset += 8

        max_ts = read_bigint64le(buffer, offset, True)
        offset += 8

        oracle_price_offset = read_int32_le(buffer, offset, True)
        offset += 4

        order_id = read_int32_le(buffer, offset, False)
        offset += 4

        market_index = read_uint16_le(buffer, offset)
        offset += 2

        order_status_num = read_uint8(buffer, offset)
        status: OrderStatus = (
            OrderStatus.Init() if order_status_num == 0 else OrderStatus.Open()
        )
        offset += 1

        order_type_num = read_uint8(buffer, offset)
        order_type: OrderType
        if order_type_num == 0:
            order_type = OrderType.Market()
        elif order_type_num == 1:
            order_type = OrderType.Limit()
        elif order_type_num == 2:
            order_type = OrderType.TriggerMarket()
        elif order_type_num == 3:
            order_type = OrderType.TriggerLimit()
        elif order_type_num == 4:
            order_type = OrderType.Oracle()
        else:
            raise ValueError(f"Invalid order type: {order_type_num}")

        offset += 1

        market_type_num = read_uint8(buffer, offset)
        market_type: MarketType = (
            MarketType.Spot() if market_type_num == 0 else MarketType.Perp()
        )
        offset += 1

        user_order_id = read_uint8(buffer, offset)
        offset += 1

        existing_position_direction_num = read_uint8(buffer, offset)
        existing_position_direction: PositionDirection = (
            PositionDirection.Long()
            if existing_position_direction_num == 0
            else PositionDirection.Short()
        )
        offset += 1

        position_direction_num = read_uint8(buffer, offset)
        direction: PositionDirection = (
            PositionDirection.Long()
            if position_direction_num == 0
            else PositionDirection.Short()
        )
        offset += 1

        reduce_only = read_uint8(buffer, offset) == 1
        offset += 1

        post_only = read_uint8(buffer, offset) == 1
        offset += 1

        immediate_or_cancel = read_uint8(buffer, offset) == 1
        offset += 1

        trigger_condition_num = read_uint8(buffer, offset)
        trigger_condition: OrderTriggerCondition
        if trigger_condition_num == 0:
            trigger_condition = OrderTriggerCondition.Above()
        elif trigger_condition_num == 1:
            trigger_condition = OrderTriggerCondition.Below()
        elif trigger_condition_num == 2:
            trigger_condition = OrderTriggerCondition.TriggeredAbove()
        elif trigger_condition_num == 3:
            trigger_condition = OrderTriggerCondition.TriggeredBelow()
        offset += 1

        auction_duration = read_uint8(buffer, offset)
        offset += 1
        posted_slot_tail = read_uint8(buffer, offset)
        offset += 1
        bit_flags = read_uint8(buffer, offset)
        offset += 1
        offset += 1  # padding

        orders.append(
            Order(
                slot=slot,
                price=price,
                base_asset_amount=base_asset_amount,
                base_asset_amount_filled=base_asset_amount_filled,
                quote_asset_amount_filled=quote_asset_amount_filled,
                trigger_price=trigger_price,
                auction_start_price=auction_start_price,
                auction_end_price=auction_end_price,
                max_ts=max_ts,
                oracle_price_offset=oracle_price_offset,
                order_id=order_id,
                market_index=market_index,
                status=status,
                order_type=order_type,
                market_type=market_type,
                user_order_id=user_order_id,
                existing_position_direction=existing_position_direction,
                direction=direction,
                reduce_only=reduce_only,
                post_only=post_only,
                immediate_or_cancel=immediate_or_cancel,
                trigger_condition=trigger_condition,
                auction_duration=auction_duration,
                bit_flags=bit_flags,
                posted_slot_tail=posted_slot_tail,
                padding=[0],
            )
        )

    last_add_perp_lp_shares_ts = read_bigint64le(buffer, offset, signed=True)
    offset += 8

    total_deposits = read_bigint64le(buffer, offset, signed=False)
    offset += 8

    total_withdraws = read_bigint64le(buffer, offset, signed=False)
    offset += 8

    total_social_loss = read_bigint64le(buffer, offset, signed=False)
    offset += 8

    settled_perp_pnl = read_bigint64le(buffer, offset, signed=True)
    offset += 8

    cumulative_spot_fees = read_bigint64le(buffer, offset, signed=True)
    offset += 8

    cumulative_perp_funding = read_bigint64le(buffer, offset, signed=True)
    offset += 8

    liquidation_margin_freed = read_bigint64le(buffer, offset, signed=False)
    offset += 8

    last_active_slot = read_bigint64le(buffer, offset, signed=False)
    offset += 8

    next_order_id = read_int32_le(buffer, offset, False)
    offset += 4

    max_margin_ratio = read_int32_le(buffer, offset, False)
    offset += 4

    next_liquidation_id = read_uint16_le(buffer, offset)
    offset += 2

    sub_account_id = read_uint16_le(buffer, offset)
    offset += 2

    status = read_uint8(buffer, offset)
    offset += 1

    is_margin_trading_enabled = read_uint8(buffer, offset) == 1
    offset += 1

    idle = read_uint8(buffer, offset) == 1
    offset += 1

    open_orders = read_uint8(buffer, offset)
    offset += 1

    has_open_order = read_uint8(buffer, offset) == 1
    offset += 1

    open_auctions = read_uint8(buffer, offset)
    offset += 1

    has_open_auction = read_uint8(buffer, offset) == 1
    offset += 1

    margin_mode: MarginMode
    margin_mode_num = read_uint8(buffer, offset)
    if margin_mode_num == 0:
        margin_mode = MarginMode.Default()
    else:
        margin_mode = MarginMode.HighLeverage()
    offset += 1

    pool_id = read_uint8(buffer, offset)
    offset += 1

    padding1_bytes = [buffer[offset + i] for i in range(3)]
    offset += 3

    last_fuel_bonus_update_ts = read_int32_le(buffer, offset, signed=False)
    offset += 4

    final_padding_bytes = [buffer[offset + i] for i in range(12)]
    offset += 12

    user_account_padding = padding1_bytes + final_padding_bytes

    return UserAccount(
        authority,
        delegate,
        name,
        spot_positions,
        perp_positions,
        orders,
        last_add_perp_lp_shares_ts,
        total_deposits,
        total_withdraws,
        total_social_loss,
        settled_perp_pnl,
        cumulative_spot_fees,
        cumulative_perp_funding,
        liquidation_margin_freed,
        last_active_slot,
        next_order_id,
        max_margin_ratio,
        next_liquidation_id,
        sub_account_id,
        status,
        is_margin_trading_enabled,
        idle,
        open_orders,
        has_open_order,
        open_auctions,
        has_open_auction,
        margin_mode,
        pool_id,
        last_fuel_bonus_update_ts,
        user_account_padding,
    )
