import json
from anchorpy import Program, Provider, WorkspaceType, workspace_fixture
from pytest import fixture, mark
from driftpy.decode.user import decode_user
from decode_strings import user_account_buffer_strings
from sys import getsizeof
from enum import Enum
import time
import base64
from driftpy.math.perp_position import is_available
from driftpy.math.spot_position import is_spot_position_available
from driftpy.types import Order, PerpPosition, SpotBalanceType, SpotPosition, UserAccount, is_variant

workspace = workspace_fixture(
    "protocol-v2", build_cmd="anchor build", scope="session"
)

@fixture(scope="session")
def program(workspace: WorkspaceType) -> Program:
    """Create a Program instance."""
    return workspace["drift"] 

@fixture(scope="session")
def provider(program: Program) -> Provider:
    return program.provider

@mark.asyncio
async def test_user_decode(program: Program):
    total_anchor_size: int = 0
    total_custom_size: int = 0
    total_anchor_time: int = 0
    total_custom_time: int = 0

    for index, user_account_buffer_string in enumerate(user_account_buffer_strings):
        user_account_buffer = base64.b64decode(user_account_buffer_string)
        (anchor_size, custom_size, anchor_time, custom_time) = user_account_decode(program, user_account_buffer, index)
        total_anchor_size += anchor_size
        total_custom_size += custom_size
        total_anchor_time += anchor_time
        total_custom_time += custom_time

    print("Total anchor size:", total_anchor_size)
    print("Total custom size:", total_custom_size)
    print("Total anchor time:", total_anchor_time)
    print("Total custom time:", total_custom_time)


def user_account_decode(program: Program, user_account_buffer: bytes, index: int):
    print("Benchmarking user account decode: ", index)

    anchor_start_ts = int(time.time() * 1000)
    anchor_user_account: UserAccount = program.coder.accounts.decode(user_account_buffer)
    anchor_end_ts = int(time.time() * 1000)
    anchor_time = anchor_end_ts - anchor_start_ts

    custom_start_ts = int(time.time() * 1000)
    custom_user_account = decode_user(user_account_buffer)
    custom_end_ts = int(time.time() * 1000)
    custom_time = custom_end_ts - custom_start_ts

    anchor_size = getsizeof(anchor_user_account)
    custom_size = getsizeof(custom_user_account)

    assert str(anchor_user_account.authority) == str(custom_user_account.authority)
    assert str(anchor_user_account.delegate) == str(custom_user_account.delegate)
    assert arrays_are_equal(anchor_user_account.name, custom_user_account.name)    

    anchor_spot_generator = get_spot_positions(anchor_user_account.spot_positions)
    custom_spot_generator = get_spot_positions(custom_user_account.spot_positions)

    for anchor_s, custom_s in zip_generator(anchor_spot_generator, custom_spot_generator):
        cmp_spot(anchor_s, custom_s)
        
    anchor_perp_generator = get_perp_positions(anchor_user_account.perp_positions)
    custom_perp_generator = get_perp_positions(custom_user_account.perp_positions)

    for anchor_p, custom_p in zip_generator(anchor_perp_generator, custom_perp_generator):
        cmp_perp(anchor_p, custom_p)

    anchor_order_generator = get_orders(anchor_user_account.orders)
    custom_order_generator = get_orders(custom_user_account.orders)

    for anchor_o, custom_o in zip_generator(anchor_order_generator, custom_order_generator):
        cmp_orders(anchor_o, custom_o)

    assert anchor_user_account.last_add_perp_lp_shares_ts == custom_user_account.last_add_perp_lp_shares_ts
    assert anchor_user_account.total_deposits == custom_user_account.total_deposits
    assert anchor_user_account.total_withdraws == custom_user_account.total_withdraws
    assert anchor_user_account.total_social_loss == custom_user_account.total_social_loss
    assert anchor_user_account.settled_perp_pnl == custom_user_account.settled_perp_pnl
    assert anchor_user_account.cumulative_spot_fees == custom_user_account.cumulative_spot_fees
    assert anchor_user_account.cumulative_perp_funding == custom_user_account.cumulative_perp_funding
    assert anchor_user_account.liquidation_margin_freed == custom_user_account.liquidation_margin_freed
    assert anchor_user_account.last_active_slot == custom_user_account.last_active_slot
    assert anchor_user_account.sub_account_id == custom_user_account.sub_account_id
    assert anchor_user_account.status == custom_user_account.status
    assert anchor_user_account.next_liquidation_id == custom_user_account.next_liquidation_id
    assert anchor_user_account.next_order_id == custom_user_account.next_order_id
    assert anchor_user_account.max_margin_ratio == custom_user_account.max_margin_ratio
    assert anchor_user_account.is_margin_trading_enabled == custom_user_account.is_margin_trading_enabled
    assert anchor_user_account.idle == custom_user_account.idle
    assert anchor_user_account.open_orders == custom_user_account.open_orders
    assert anchor_user_account.has_open_order == custom_user_account.has_open_order
    assert anchor_user_account.open_auctions == custom_user_account.open_auctions
    assert anchor_user_account.has_open_auction == custom_user_account.has_open_auction

    return (anchor_size, custom_size, anchor_time, custom_time)

def get_orders(orders):
    for order in orders:
        if is_variant(order.status, 'Open'):
            yield order
            
def cmp_orders(anchor: Order, custom: Order):
    assert enums_eq(anchor.status, custom.status)
    assert enums_eq(anchor.order_type, custom.order_type)
    assert enums_eq(anchor.market_type, custom.market_type)
    assert anchor.slot == custom.slot
    assert anchor.order_id == custom.order_id
    assert anchor.user_order_id == custom.user_order_id
    assert anchor.market_index == custom.market_index
    assert anchor.price == custom.price
    assert anchor.base_asset_amount == custom.base_asset_amount
    assert anchor.base_asset_amount_filled == custom.base_asset_amount_filled
    assert anchor.quote_asset_amount_filled == custom.quote_asset_amount_filled
    assert enums_eq(anchor.direction, custom.direction)
    assert anchor.reduce_only == custom.reduce_only
    assert anchor.trigger_price == custom.trigger_price
    assert enums_eq(anchor.trigger_condition, custom.trigger_condition)
    assert enums_eq(anchor.existing_position_direction, custom.existing_position_direction)
    assert anchor.post_only == custom.post_only
    assert anchor.immediate_or_cancel == custom.immediate_or_cancel
    assert anchor.oracle_price_offset == custom.oracle_price_offset
    assert anchor.auction_start_price == custom.auction_start_price
    assert anchor.auction_end_price == custom.auction_end_price
    assert anchor.max_ts == custom.max_ts

def get_perp_positions(perp_positions):
    for perp_position in perp_positions:
        if not is_available(perp_position):
            yield perp_position

def cmp_perp(anchor: PerpPosition, custom: PerpPosition):
    assert anchor.base_asset_amount == custom.base_asset_amount
    assert anchor.last_cumulative_funding_rate == custom.last_cumulative_funding_rate
    assert anchor.market_index == custom.market_index
    assert anchor.quote_asset_amount == custom.quote_asset_amount
    assert anchor.quote_entry_amount == custom.quote_entry_amount
    assert anchor.quote_break_even_amount == custom.quote_break_even_amount
    assert anchor.open_bids == custom.open_bids
    assert anchor.open_asks == custom.open_asks
    assert anchor.settled_pnl == custom.settled_pnl
    assert anchor.lp_shares == custom.lp_shares
    assert anchor.last_base_asset_amount_per_lp == custom.last_base_asset_amount_per_lp
    assert anchor.last_quote_asset_amount_per_lp == custom.last_quote_asset_amount_per_lp
    assert anchor.open_orders == custom.open_orders
    assert anchor.per_lp_base == custom.per_lp_base

def get_spot_positions(spot_positions):
    for spot_position in spot_positions:
        if not is_spot_position_available(spot_position):
            yield spot_position

def cmp_spot(anchor: SpotPosition, custom: SpotPosition):
    assert anchor.market_index == custom.market_index
    assert enums_eq(anchor.balance_type, custom.balance_type)
    assert anchor.open_orders == custom.open_orders
    assert anchor.scaled_balance == custom.scaled_balance
    assert anchor.open_bids == custom.open_bids
    assert anchor.open_asks == custom.open_asks
    assert anchor.cumulative_deposits == custom.cumulative_deposits
    
def arrays_are_equal(arr1, arr2):
    if len(arr1) != len(arr2):
        return False

    for i in range(len(arr1)):
        if arr1[i] != arr2[i]:
            return False

    return True

def enums_eq(e1, e2):
    return str(e1) == str(e2)

def zip_generator(gen1, gen2):
    try:
        while True:
            value1 = next(gen1)
            value2 = next(gen2)
            yield (value1, value2)
    except StopIteration:
        try:
            next(gen1)
            # If this line is reached, gen1 has more items than gen2
            raise ValueError('Generators have different lengths')
        except StopIteration:
            pass

        try:
            next(gen2)
            raise ValueError('Generators have different lengths')
        except StopIteration:
            pass