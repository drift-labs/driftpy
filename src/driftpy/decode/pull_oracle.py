from driftpy.decode.user import (
    read_uint8,
    read_int32_le,
    read_bigint64le,
)
from driftpy.types import PriceUpdateV2, PriceFeedMessage


def decode_pull_oracle(buffer: bytes) -> PriceUpdateV2:
    offset = 8

    offset += 32  # skip 0

    verification_level_flag = read_uint8(buffer, offset)
    if verification_level_flag & 0x1:
        offset += 1  # skip verification_level Full
    else:
        offset += 2  # skip verificaton_level Partial

    offset += 32  # skip feed_id

    price = read_bigint64le(buffer, offset, True)
    offset += 8

    conf = read_bigint64le(buffer, offset, False)
    offset += 8

    exponent = read_int32_le(buffer, offset, True)
    offset += 4

    offset += 8  # skip publish_time
    offset += 8  # skip prev_publish_time

    ema_price = read_bigint64le(buffer, offset, True)
    offset += 8

    ema_conf = read_bigint64le(buffer, offset, False)
    offset += 8

    posted_slot = read_bigint64le(buffer, offset, False)

    price_feed_message = PriceFeedMessage(price, conf, exponent, ema_price, ema_conf)

    return PriceUpdateV2(price_feed_message, posted_slot)
