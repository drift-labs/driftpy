from driftpy.constants.numeric_constants import PRICE_PRECISION


def convert_to_number(big_number, precision=PRICE_PRECISION):
    if not big_number:
        return 0
    return big_number // precision + (big_number % precision) / precision
