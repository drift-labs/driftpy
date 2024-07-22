from driftpy.decode.user import (
    read_uint8,
    read_uint16_le,
    read_bigint64le,
)
from driftpy.types import UserStatsAccount, UserFees
from solders.pubkey import Pubkey


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

    next_epoch_ts = read_bigint64le(buffer, offset, False)
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

    last_filler_volume_30d_ts = read_bigint64le(buffer, offset, False)
    offset += 8

    if_staked_quote_asset_amount = read_bigint64le(buffer, offset, False)
    offset += 8

    number_of_sub_accounts = read_uint16_le(buffer, offset)
    offset += 2

    number_of_sub_accounts_created = read_uint16_le(buffer, offset)
    offset += 2

    is_referrer = read_uint8(buffer, offset) == 1
    offset += 1

    disable_update_perp_bid_ask_twap = read_uint8(buffer, offset) == 1
    offset += 1

    padding = [0] * 50

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
        padding,
    )
