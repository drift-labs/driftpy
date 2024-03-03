from pytest import mark

from driftpy.math.utils import time_remaining_until_update


@mark.asyncio
async def test_time_remaining_updates():
    now = 1_683_576_852
    last_update = 1_683_576_000
    period = 3_600

    tr = time_remaining_until_update(now, last_update, period)
    assert tr == 2_748

    tr = time_remaining_until_update(now, last_update - period, period)
    assert tr == 0

    too_late = last_update - ((period // 3) + 1)
    tr = time_remaining_until_update(too_late + 1, too_late, period)
    assert tr == 4_800

    tr = time_remaining_until_update(now, last_update + 1, period)
    assert tr == 2_748

    tr = time_remaining_until_update(now, last_update - 1, period)
    assert tr == 2_748
