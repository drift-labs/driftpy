def clamp_num(x: int, min_clamp: int, max_clamp: int) -> int:
    return max(min_clamp, min(x, max_clamp))