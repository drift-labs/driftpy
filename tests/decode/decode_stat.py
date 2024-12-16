import base64
import time
from pathlib import Path

from anchorpy import Idl, Program
from pytest import fixture, mark
from solders.pubkey import Pubkey

import driftpy
from driftpy.decode.user_stat import decode_user_stat
from driftpy.types import UserStatsAccount
from tests.decode.stat_decode_strings import stats


@fixture(scope="session")
def program() -> Program:
    file = Path(str(driftpy.__path__[0]) + "/idl/drift.json")
    with file.open() as f:
        raw = file.read_text()
    idl = Idl.from_json(raw)
    return Program(
        idl,
        Pubkey.from_string("dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH"),
    )


@mark.asyncio
async def test_user_stat_decode(program: Program):
    total_anchor_time: int = 0
    total_custom_time: int = 0

    for index, stat in enumerate(stats):
        stat_bytes = base64.b64decode(stat)
        (anchor_time, custom_time) = user_stats_decode(program, stat_bytes, index)
        total_anchor_time += anchor_time
        total_custom_time += custom_time

    print("Total anchor time:", total_anchor_time)
    print("Total custom time:", total_custom_time)


def user_stats_decode(program: Program, buffer: bytes, index: int):
    print("Benchmarking user stats decode: ", index)

    anchor_start_ts = int(time.time() * 1_000)
    anchor_user_stats: UserStatsAccount = program.coder.accounts.decode(buffer)
    anchor_end_ts = int(time.time() * 1_000)
    anchor_time = anchor_end_ts - anchor_start_ts

    custom_start_ts = int(time.time() * 1_000)
    custom_user_stats = decode_user_stat(buffer)
    custom_end_ts = int(time.time() * 1_000)
    custom_time = custom_end_ts - custom_start_ts

    assert str(anchor_user_stats.authority) == str(custom_user_stats.authority)
    assert str(anchor_user_stats.referrer) == str(custom_user_stats.referrer)
    assert (
        anchor_user_stats.fees.total_fee_paid == custom_user_stats.fees.total_fee_paid
    )
    assert (
        anchor_user_stats.fees.total_fee_rebate
        == custom_user_stats.fees.total_fee_rebate
    )
    assert (
        anchor_user_stats.fees.total_token_discount
        == custom_user_stats.fees.total_token_discount
    )
    assert (
        anchor_user_stats.fees.total_referee_discount
        == custom_user_stats.fees.total_referee_discount
    )
    assert (
        anchor_user_stats.fees.total_referrer_reward
        == custom_user_stats.fees.total_referrer_reward
    )
    assert (
        anchor_user_stats.fees.current_epoch_referrer_reward
        == custom_user_stats.fees.current_epoch_referrer_reward
    )
    assert anchor_user_stats.next_epoch_ts == custom_user_stats.next_epoch_ts
    assert anchor_user_stats.maker_volume30d == custom_user_stats.maker_volume30d
    assert anchor_user_stats.taker_volume30d == custom_user_stats.taker_volume30d
    assert anchor_user_stats.filler_volume30d == custom_user_stats.filler_volume30d
    assert (
        anchor_user_stats.last_maker_volume30d_ts
        == custom_user_stats.last_maker_volume30d_ts
    )
    assert (
        anchor_user_stats.last_taker_volume30d_ts
        == custom_user_stats.last_taker_volume30d_ts
    )
    assert (
        anchor_user_stats.last_filler_volume30d_ts
        == custom_user_stats.last_filler_volume30d_ts
    )
    assert (
        anchor_user_stats.if_staked_quote_asset_amount
        == custom_user_stats.if_staked_quote_asset_amount
    )
    assert (
        anchor_user_stats.number_of_sub_accounts
        == custom_user_stats.number_of_sub_accounts
    )
    assert (
        anchor_user_stats.number_of_sub_accounts_created
        == custom_user_stats.number_of_sub_accounts_created
    )
    # assert anchor_user_stats.is_referrer == custom_user_stats.is_referrer
    assert (
        anchor_user_stats.disable_update_perp_bid_ask_twap
        == custom_user_stats.disable_update_perp_bid_ask_twap
    )

    return (anchor_time, custom_time)
