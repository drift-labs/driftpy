from driftpy.types import (
    MarketType,
    OrderParams,
    OrderTriggerCondition,
    OrderType,
    PositionDirection,
    PostOnlyParams,
    SignedMsgOrderParamsMessage,
    SignedMsgTriggerOrderParams,
)


def read_bool(byte: int) -> bool:
    return byte != 0


def read_uint8(buffer, offset):
    return buffer[offset]


def read_uint16_le(buffer, offset):
    return int.from_bytes(buffer[offset : offset + 2], byteorder="little")


def read_int32_le(buffer, offset, signed):
    return int.from_bytes(
        buffer[offset : offset + 4], byteorder="little", signed=signed
    )


def read_bigint64le(buffer, offset, signed):
    return int.from_bytes(
        buffer[offset : offset + 8], byteorder="little", signed=signed
    )


def decode_order_params(buffer: bytes) -> OrderParams:
    offset = 0

    def debug_read(size: int, field_name: str, signed: bool = False) -> bytes:
        nonlocal offset
        if offset + size > len(buffer):
            raise ValueError(
                f"Buffer overflow reading {field_name} at offset {offset}, need {size} bytes, buffer length {len(buffer)}"
            )
        value = buffer[offset : offset + size]
        offset += size
        return value

    order_type_num = int.from_bytes(debug_read(1, "order_type"), "little")
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

    market_type_num = int.from_bytes(debug_read(1, "market_type"), "little")
    market_type: MarketType = (
        MarketType.Spot() if market_type_num == 0 else MarketType.Perp()
    )

    existing_position_direction_num = int.from_bytes(
        debug_read(1, "direction"), "little"
    )
    direction: PositionDirection = (
        PositionDirection.Long()
        if existing_position_direction_num == 0
        else PositionDirection.Short()
    )

    user_order_id = int.from_bytes(debug_read(1, "user_order_id"), "little")

    base_asset_amount = int.from_bytes(debug_read(8, "base_asset_amount"), "little")

    price = int.from_bytes(debug_read(8, "price"), "little")

    # marketIndex (u16)
    market_index = int.from_bytes(debug_read(2, "market_index"), "little")

    # reduceOnly (bool)
    reduce_only = int.from_bytes(debug_read(1, "reduce_only"), "little") == 1

    # PostOnlyParam (u8 enum)
    post_only_num = int.from_bytes(debug_read(1, "post_only"), "little")
    post_only: PostOnlyParams
    if post_only_num == 0:
        post_only = PostOnlyParams.NONE()
    elif post_only_num == 1:
        post_only = PostOnlyParams.MustPostOnly()
    elif post_only_num == 2:
        post_only = PostOnlyParams.TryPostOnly()
    elif post_only_num == 3:
        post_only = PostOnlyParams.Slide()

    # immediateOrCancel (bool)
    immediate_or_cancel = (
        int.from_bytes(debug_read(1, "immediate_or_cancel"), "little") == 1
    )

    # maxTs (option<i64>)
    max_ts_present = int.from_bytes(debug_read(1, "max_ts_present"), "little")
    max_ts = None
    if max_ts_present == 1:
        max_ts = int.from_bytes(debug_read(8, "max_ts"), "little", signed=True)

    # triggerPrice (option<u64>)
    trigger_price_present = int.from_bytes(
        debug_read(1, "trigger_price_present"), "little"
    )
    trigger_price = None
    if trigger_price_present == 1:
        trigger_price = int.from_bytes(debug_read(8, "trigger_price"), "little")

    # OrderTriggerCondition (u8 enum)
    trigger_condition_num = int.from_bytes(debug_read(1, "trigger_condition"), "little")
    trigger_condition: OrderTriggerCondition
    if trigger_condition_num == 0:
        trigger_condition = OrderTriggerCondition.Above()
    elif trigger_condition_num == 1:
        trigger_condition = OrderTriggerCondition.Below()
    elif trigger_condition_num == 2:
        trigger_condition = OrderTriggerCondition.TriggeredAbove()
    elif trigger_condition_num == 3:
        trigger_condition = OrderTriggerCondition.TriggeredBelow()

    # oraclePriceOffset (option<i32>)
    oracle_offset_present = int.from_bytes(
        debug_read(1, "oracle_offset_present"), "little"
    )
    oracle_price_offset = None
    if oracle_offset_present == 1:
        oracle_price_offset = int.from_bytes(
            debug_read(4, "oracle_price_offset"), "little", signed=True
        )

    # auctionDuration (option<u8>)
    auction_duration_present = int.from_bytes(
        debug_read(1, "auction_duration_present"), "little"
    )
    auction_duration = None
    if auction_duration_present == 1:
        auction_duration = int.from_bytes(debug_read(1, "auction_duration"), "little")

    # auctionStartPrice (option<i64>)
    auction_start_present = int.from_bytes(
        debug_read(1, "auction_start_present"), "little"
    )
    auction_start_price = None
    if auction_start_present == 1:
        auction_start_price = int.from_bytes(
            debug_read(8, "auction_start_price"), "little", signed=True
        )

    # auctionEndPrice (option<i64>)
    auction_end_present = int.from_bytes(debug_read(1, "auction_end_present"), "little")
    auction_end_price = None
    if auction_end_present == 1:
        auction_end_price = int.from_bytes(
            debug_read(8, "auction_end_price"), "little", signed=True
        )

    return OrderParams(
        order_type=order_type,
        market_type=market_type,
        direction=direction,
        user_order_id=user_order_id,
        base_asset_amount=base_asset_amount,
        price=price,
        market_index=market_index,
        reduce_only=reduce_only,
        post_only=post_only,
        immediate_or_cancel=immediate_or_cancel,
        max_ts=max_ts,
        trigger_price=trigger_price,
        trigger_condition=trigger_condition,
        oracle_price_offset=oracle_price_offset,
        auction_duration=auction_duration,
        auction_start_price=auction_start_price,
        auction_end_price=auction_end_price,
    )


def decode_signed_msg_trigger_params(buffer: bytes) -> SignedMsgTriggerOrderParams:
    offset = 0

    trigger_price = int.from_bytes(buffer[offset : offset + 8], "little")
    offset += 8

    base_asset_amount = int.from_bytes(buffer[offset : offset + 8], "little")
    offset += 8

    return SignedMsgTriggerOrderParams(
        trigger_price=trigger_price, base_asset_amount=base_asset_amount
    )


def decode_signed_msg_order_params_message(
    buffer: bytes,
) -> SignedMsgOrderParamsMessage:
    signed_msg_order_params_buf = buffer[8:]

    order_params, bytes_read = decode_order_params_with_size(
        signed_msg_order_params_buf
    )
    offset = bytes_read

    sub_account_id = read_uint16_le(signed_msg_order_params_buf, offset)
    offset += 2

    slot = read_bigint64le(signed_msg_order_params_buf, offset, False)
    offset += 8

    uuid = signed_msg_order_params_buf[offset : offset + 8]
    offset += 8

    take_profit_present = read_uint8(signed_msg_order_params_buf, offset)
    offset += 1
    take_profit = None
    if take_profit_present == 1:
        take_profit = decode_signed_msg_trigger_params(
            signed_msg_order_params_buf[offset : offset + 16]
        )
        offset += 16

    stop_loss_present = read_uint8(signed_msg_order_params_buf, offset)
    offset += 1
    stop_loss = None
    if stop_loss_present == 1:
        stop_loss = decode_signed_msg_trigger_params(
            signed_msg_order_params_buf[offset : offset + 16]
        )
        offset += 16

    return SignedMsgOrderParamsMessage(
        signed_msg_order_params=order_params,
        sub_account_id=sub_account_id,
        slot=slot,
        uuid=uuid,
        take_profit_order_params=take_profit,
        stop_loss_order_params=stop_loss,
    )


def read_bytes(buffer, offset, size):
    if offset + size > len(buffer):
        raise ValueError(
            f"Buffer overflow at offset {offset}, need {size} bytes, buffer length {len(buffer)}"
        )
    value = buffer[offset : offset + size]
    return value, offset + size


def decode_order_params_with_size(buffer: bytes) -> tuple[OrderParams, int]:
    offset = 0

    # Read order_type (u8)
    order_type_num = int.from_bytes(buffer[offset : offset + 1], "little")
    offset += 1

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

    # Read market_type (u8)
    market_type_num = int.from_bytes(buffer[offset : offset + 1], "little")
    offset += 1
    market_type = MarketType.Spot() if market_type_num == 0 else MarketType.Perp()

    # Read direction (u8)
    direction_num = int.from_bytes(buffer[offset : offset + 1], "little")
    offset += 1
    direction = (
        PositionDirection.Long() if direction_num == 0 else PositionDirection.Short()
    )

    # Read user_order_id (u8)
    user_order_id = int.from_bytes(buffer[offset : offset + 1], "little")
    offset += 1

    # Read base_asset_amount (u64)
    base_asset_amount = int.from_bytes(buffer[offset : offset + 8], "little")
    offset += 8

    # Read price (u64)
    price = int.from_bytes(buffer[offset : offset + 8], "little")
    offset += 8

    # Read market_index (u16)
    market_index = int.from_bytes(buffer[offset : offset + 2], "little")
    offset += 2

    # Read reduce_only (bool)
    reduce_only = int.from_bytes(buffer[offset : offset + 1], "little") == 1
    offset += 1

    # Read post_only (u8 enum)
    post_only_num = int.from_bytes(buffer[offset : offset + 1], "little")
    offset += 1

    if post_only_num == 0:
        post_only = PostOnlyParams.NONE()
    elif post_only_num == 1:
        post_only = PostOnlyParams.MustPostOnly()
    elif post_only_num == 2:
        post_only = PostOnlyParams.TryPostOnly()
    elif post_only_num == 3:
        post_only = PostOnlyParams.Slide()

    # Read immediate_or_cancel (bool)
    immediate_or_cancel = int.from_bytes(buffer[offset : offset + 1], "little") == 1
    offset += 1

    # Read max_ts (option<i64>)
    max_ts_present = int.from_bytes(buffer[offset : offset + 1], "little")
    offset += 1

    max_ts = None
    if max_ts_present == 1:
        max_ts = int.from_bytes(buffer[offset : offset + 8], "little", signed=True)
        offset += 8

    # Read trigger_price (option<u64>)
    trigger_price_present = int.from_bytes(buffer[offset : offset + 1], "little")
    offset += 1

    trigger_price = None
    if trigger_price_present == 1:
        trigger_price = int.from_bytes(buffer[offset : offset + 8], "little")
        offset += 8

    # Read trigger_condition (u8 enum)
    trigger_condition_num = int.from_bytes(buffer[offset : offset + 1], "little")
    offset += 1

    if trigger_condition_num == 0:
        trigger_condition = OrderTriggerCondition.Above()
    elif trigger_condition_num == 1:
        trigger_condition = OrderTriggerCondition.Below()
    elif trigger_condition_num == 2:
        trigger_condition = OrderTriggerCondition.TriggeredAbove()
    elif trigger_condition_num == 3:
        trigger_condition = OrderTriggerCondition.TriggeredBelow()

    # Read oracle_price_offset (option<i32>)
    oracle_offset_present = int.from_bytes(buffer[offset : offset + 1], "little")
    offset += 1

    oracle_price_offset = None
    if oracle_offset_present == 1:
        oracle_price_offset = int.from_bytes(
            buffer[offset : offset + 4], "little", signed=True
        )
        offset += 4

    # Read auction_duration (option<u8>)
    auction_duration_present = int.from_bytes(buffer[offset : offset + 1], "little")
    offset += 1

    auction_duration = None
    if auction_duration_present == 1:
        auction_duration = int.from_bytes(buffer[offset : offset + 1], "little")
        offset += 1

    # Read auction_start_price (option<i64>)
    auction_start_present = int.from_bytes(buffer[offset : offset + 1], "little")
    offset += 1

    auction_start_price = None
    if auction_start_present == 1:
        auction_start_price = int.from_bytes(
            buffer[offset : offset + 8], "little", signed=True
        )
        offset += 8

    # Read auction_end_price (option<i64>)
    auction_end_present = int.from_bytes(buffer[offset : offset + 1], "little")
    offset += 1

    auction_end_price = None
    if auction_end_present == 1:
        auction_end_price = int.from_bytes(
            buffer[offset : offset + 8], "little", signed=True
        )
        offset += 8

    return OrderParams(
        order_type=order_type,
        market_type=market_type,
        direction=direction,
        user_order_id=user_order_id,
        base_asset_amount=base_asset_amount,
        price=price,
        market_index=market_index,
        reduce_only=reduce_only,
        post_only=post_only,
        immediate_or_cancel=immediate_or_cancel,
        max_ts=max_ts,
        trigger_price=trigger_price,
        trigger_condition=trigger_condition,
        oracle_price_offset=oracle_price_offset,
        auction_duration=auction_duration,
        auction_start_price=auction_start_price,
        auction_end_price=auction_end_price,
    ), offset
