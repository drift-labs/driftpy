import base58
from anchorpy.coder.accounts import _account_discriminator
from solana.rpc.types import MemcmpOpts

def get_user_filter() -> MemcmpOpts:
    return MemcmpOpts(0, base58.b58encode(_account_discriminator('User')).decode())

def get_non_idle_user_filter() -> MemcmpOpts:
    return MemcmpOpts(4350, base58.b58encode(bytes([0])).decode())

def get_user_with_auction_filter() -> MemcmpOpts:
    return MemcmpOpts(4354, base58.b58encode(bytes([1])).decode())