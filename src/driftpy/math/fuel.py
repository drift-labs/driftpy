from typing import Final
from driftpy.types import SpotMarketAccount, PerpMarketAccount
from driftpy.constants.numeric_constants import QUOTE_PRECISION, FUEL_WINDOW

_SCALE_10: Final[int] = QUOTE_PRECISION // 10
_DENOM: Final[int] = FUEL_WINDOW * _SCALE_10

def _scaled_fuel(value_abs: int, fuel_bonus_numerator: int, boost: int) -> int:
    if value_abs == 0 or fuel_bonus_numerator == 0 or boost == 0:
        return 0

    return (value_abs * fuel_bonus_numerator * boost) // _DENOM


def calculate_insurance_fuel_bonus(
    spot_market: SpotMarketAccount, token_stake_amount: int, fuel_bonus_numerator: int
) -> int:
    value_abs = abs(token_stake_amount)
    return _scaled_fuel(value_abs, fuel_bonus_numerator, spot_market.fuel_boost_insurance)


def calculate_spot_fuel_bonus(
    spot_market: SpotMarketAccount, signed_token_value: int, fuel_bonus_numerator: int
) -> int:
    value_abs = abs(signed_token_value)

    if value_abs <= QUOTE_PRECISION:
        return 0

    boost = spot_market.fuel_boost_deposits if signed_token_value > 0 else spot_market.fuel_boost_borrows
    return _scaled_fuel(value_abs, fuel_bonus_numerator, boost)


def calculate_perp_fuel_bonus(
    perp_market: PerpMarketAccount, base_asset_value: int, fuel_bonus_numerator: int
) -> int:
    value_abs = abs(base_asset_value)

    if value_abs <= QUOTE_PRECISION:
        return 0

    return _scaled_fuel(value_abs, fuel_bonus_numerator, perp_market.fuel_boost_position)