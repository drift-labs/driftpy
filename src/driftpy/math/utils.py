def clamp_num(x: int, min_clamp: int, max_clamp: int) -> int:
    return max(min_clamp, min(x, max_clamp))


def div_ceil(a: int, b: int) -> int:
    if b == 0:
        return a

    quotient = a // b
    remainder = a % b

    if remainder > 0:
        quotient += 1

    return quotient


def sig_num(x: int) -> int:
    return -1 if x < 0 else 1


def time_remaining_until_update(now: int, last_update_ts: int, update_period: int):
    time_since_last_update = now - last_update_ts

    next_update_wait = update_period
    if update_period > 1:
        last_update_delay = last_update_ts % update_period

        if not last_update_ts == 0:
            max_delay_for_next_period = update_period // 3

            two_funding_periods = update_period * 2

            if last_update_delay > max_delay_for_next_period:
                next_update_wait = two_funding_periods - last_update_delay
            else:
                next_update_wait = update_period - last_update_delay

            if next_update_wait > two_funding_periods:
                next_update_wait = next_update_wait - update_period

    if next_update_wait - time_since_last_update < 0:
        time_remaining_until_update = 0
    else:
        time_remaining_until_update = next_update_wait - time_since_last_update

    return time_remaining_until_update
