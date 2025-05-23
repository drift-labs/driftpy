from solders.pubkey import Pubkey

from driftpy.decode.user import (
    read_bigint64le,
    read_int32_le,
    read_uint8,
    read_uint16_le,
)
from driftpy.types import UserFees, UserStatsAccount


def decode_user_stat(buffer: bytes) -> UserStatsAccount:
    offset = 8
    authority = Pubkey(buffer[offset : offset + 32])
    offset += 32
    referrer = Pubkey(buffer[offset : offset + 32])
    offset += 32

    total_fee_paid = read_bigint64le(buffer, offset, False)
    offset += 8
    total_fee_rebate = read_bigint64le(buffer, offset, False)
    offset += 8
    total_token_discount = read_bigint64le(buffer, offset, False)
    offset += 8
    total_referee_discount = read_bigint64le(buffer, offset, False)
    offset += 8
    total_referrer_reward = read_bigint64le(buffer, offset, False)
    offset += 8
    current_epoch_referrer_reward = read_bigint64le(buffer, offset, False)
    offset += 8

    user_fees = UserFees(
        total_fee_paid,
        total_fee_rebate,
        total_token_discount,
        total_referee_discount,
        total_referrer_reward,
        current_epoch_referrer_reward,
    )

    next_epoch_ts = read_bigint64le(buffer, offset, True)
    offset += 8

    maker_volume_30d = read_bigint64le(buffer, offset, False)
    offset += 8

    taker_volume_30d = read_bigint64le(buffer, offset, False)
    offset += 8

    filler_volume_30d = read_bigint64le(buffer, offset, False)
    offset += 8

    last_maker_volume_30d_ts = read_bigint64le(buffer, offset, True)
    offset += 8

    last_taker_volume_30d_ts = read_bigint64le(buffer, offset, True)
    offset += 8

    last_filler_volume_30d_ts = read_bigint64le(buffer, offset, True)
    offset += 8

    if_staked_quote_asset_amount = read_bigint64le(buffer, offset, False)
    offset += 8

    number_of_sub_accounts = read_uint16_le(buffer, offset)
    offset += 2

    number_of_sub_accounts_created = read_uint16_le(buffer, offset)
    offset += 2

    referrer_status = read_uint8(buffer, offset)
    is_referrer = (referrer_status & 0x1) == 1
    offset += 1

    disable_update_perp_bid_ask_twap = read_uint8(buffer, offset) == 1
    offset += 1

    offset += 1

    fuel_overflow_status = read_uint8(buffer, offset)
    offset += 1

    fuel_insurance = read_int32_le(buffer, offset, False)
    offset += 4

    fuel_deposits = read_int32_le(buffer, offset, False)
    offset += 4

    fuel_borrows = read_int32_le(buffer, offset, False)
    offset += 4

    fuel_positions = read_int32_le(buffer, offset, False)
    offset += 4

    fuel_taker = read_int32_le(buffer, offset, False)
    offset += 4

    fuel_maker = read_int32_le(buffer, offset, False)
    offset += 4

    if_staked_gov_token_amount = read_bigint64le(buffer, offset, False)
    offset += 8

    last_fuel_if_bonus_update_ts = read_int32_le(buffer, offset, False)
    offset += 4

    padding = [0] * 12

    return UserStatsAccount(
        authority,
        referrer,
        user_fees,
        next_epoch_ts,
        maker_volume_30d,
        taker_volume_30d,
        filler_volume_30d,
        last_maker_volume_30d_ts,
        last_taker_volume_30d_ts,
        last_filler_volume_30d_ts,
        if_staked_quote_asset_amount,
        number_of_sub_accounts,
        number_of_sub_accounts_created,
        is_referrer,
        disable_update_perp_bid_ask_twap,
        fuel_overflow_status,
        fuel_insurance,
        fuel_deposits,
        fuel_borrows,
        fuel_positions,
        fuel_taker,
        fuel_maker,
        if_staked_gov_token_amount,
        last_fuel_if_bonus_update_ts,
        padding,
    )
