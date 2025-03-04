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


def time_remaining_until_update(now: int, last_update_ts: int, update_period: int) -> int:
    if update_period <= 0:
        raise ValueError("update_period must be positive")

    time_since = now - last_update_ts

    if update_period == 1:
        return max(0, 1 - time_since)

    # Calculate delay-based adjustment
    last_delay = last_update_ts % update_period
    max_delay = update_period // 3
    next_wait = update_period - last_delay

    if last_delay > max_delay:
        next_wait = 2 * update_period - last_delay

    return max(0, next_wait - time_since)
