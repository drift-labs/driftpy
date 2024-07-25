from driftpy.types import SpotMarketAccount, PerpMarketAccount
from driftpy.constants.numeric_constants import QUOTE_PRECISION, FUEL_WINDOW


def calculate_insurance_fuel_bonus(
    spot_market: SpotMarketAccount, token_stake_amount: int, fuel_bonus_numerator: int
) -> int:
    insurance_fund_fuel = (
        abs(token_stake_amount) * fuel_bonus_numerator
    ) * spot_market.fuel_boost_insurance
    insurace_fund_fuel_per_day = insurance_fund_fuel // FUEL_WINDOW
    insurance_fund_fuel_scaled = insurace_fund_fuel_per_day // (QUOTE_PRECISION // 10)

    return insurance_fund_fuel_scaled


def calculate_spot_fuel_bonus(
    spot_market: SpotMarketAccount, signed_token_value: int, fuel_bonus_numerator: int
) -> int:
    spot_fuel_scaled: int

    # dust
    if abs(signed_token_value) <= QUOTE_PRECISION:
        spot_fuel_scaled = 0
    elif signed_token_value > 0:
        deposit_fuel = (
            abs(signed_token_value) * fuel_bonus_numerator
        ) * spot_market.fuel_boost_deposits
        deposit_fuel_per_day = deposit_fuel // FUEL_WINDOW
        spot_fuel_scaled = deposit_fuel_per_day // (QUOTE_PRECISION // 10)
    else:
        borrow_fuel = (
            abs(signed_token_value) * fuel_bonus_numerator
        ) * spot_market.fuel_boost_borrows
        borrow_fuel_per_day = borrow_fuel // FUEL_WINDOW
        spot_fuel_scaled = borrow_fuel_per_day // (QUOTE_PRECISION // 10)

    return spot_fuel_scaled


def calculate_perp_fuel_bonus(
    perp_market: PerpMarketAccount, base_asset_value: int, fuel_bonus_numerator: int
) -> int:
    perp_fuel_scaled: int

    # dust
    if abs(base_asset_value) <= QUOTE_PRECISION:
        perp_fuel_scaled = 0
    else:
        perp_fuel = (
            abs(base_asset_value) * fuel_bonus_numerator
        ) * perp_market.fuel_boost_position
        perp_fuel_per_day = perp_fuel // FUEL_WINDOW
        perp_fuel_scaled = perp_fuel_per_day // (QUOTE_PRECISION // 10)

    return perp_fuel_scaled
