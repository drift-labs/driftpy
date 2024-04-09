import base58
from anchorpy.coder.accounts import _account_discriminator
from solana.rpc.types import MemcmpOpts

from driftpy.types import MarketType, is_variant


def get_user_filter() -> MemcmpOpts:
    return MemcmpOpts(0, base58.b58encode(_account_discriminator("User")).decode())


def get_non_idle_user_filter() -> MemcmpOpts:
    return MemcmpOpts(4350, base58.b58encode(bytes([0])).decode())


def get_user_with_auction_filter() -> MemcmpOpts:
    return MemcmpOpts(4354, base58.b58encode(bytes([1])).decode())


def get_market_type_filter(market_type: MarketType) -> MemcmpOpts:
    if is_variant(market_type, "Perp"):
        return MemcmpOpts(
            0, base58.b58encode(_account_discriminator("PerpMarket")).decode()
        )
    else:
        return MemcmpOpts(
            0, base58.b58encode(_account_discriminator("SpotMarket")).decode()
        )


def get_user_stats_filter() -> MemcmpOpts:
    return MemcmpOpts(0, base58.b58encode(_account_discriminator("UserStats")).decode())
