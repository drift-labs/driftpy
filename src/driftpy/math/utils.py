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
    time_since_last_update = now - last_update_ts
    
    if update_period == 1 or last_update_ts == 0:
        time_remaining = update_period - time_since_last_update
    else:
        last_update_delay = last_update_ts % update_period
        max_delay_for_next_period = update_period // 3
        
        if last_update_delay > max_delay_for_next_period:
            correction_factor = 2
        else:
            correction_factor = 1
            
        time_remaining = correction_factor * update_period - time_since_last_update - last_update_delay
        
    return max(0, time_remaining)
