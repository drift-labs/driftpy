def clamp_num(x: int, min_clamp: int, max_clamp: int) -> int:
    return max(min_clamp, min(x, max_clamp))


def div_ceil(a: int, b: int) -> int:
    if b == 0:
        return a

    quotient = a // b
    remainder = a % b

    if remainder > 0:
        return quotient + 1
    else:
        return quotient
