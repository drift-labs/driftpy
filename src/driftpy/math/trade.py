from datetime import time
from typing import Optional

from driftpy.types import UserStatsAccount


def get_user_30d_rolling_volume_estimate(
    user_stats: UserStatsAccount, now: Optional[int] = None
) -> int:
    """Estimate user's rolling 30d volume combining maker/taker with linear decay.

    Returns value in QUOTE_PRECISION units.
    """
    now = now or int(time.time())

    thirty_days = 60 * 60 * 24 * 30
    since_last_taker = max(now - user_stats.last_taker_volume30d_ts, 0)
    since_last_maker = max(now - user_stats.last_maker_volume30d_ts, 0)

    taker_component = (
        user_stats.taker_volume30d * max(thirty_days - since_last_taker, 0)
    ) // thirty_days
    maker_component = (
        user_stats.maker_volume30d * max(thirty_days - since_last_maker, 0)
    ) // thirty_days

    return taker_component + maker_component
