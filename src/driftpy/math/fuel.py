from driftpy.types import SpotMarketAccount, PerpMarketAccount
from driftpy.constants.numeric_constants import QUOTE_PRECISION, FUEL_WINDOW

SCALED_QUOTE_PRECISION = QUOTE_PRECISION // 10

def calculate_scaled_fuel(value: int, boost: float, fuel_bonus_numerator: int) -> int:
    """
    Calculate scaled fuel value.

    Args:
        value (int): The base value for calculation.
        boost (float): The boost factor.
        fuel_bonus_numerator (int): The fuel bonus numerator.

    Returns:
        int: The calculated scaled fuel value.
    """
    fuel = abs(value) * fuel_bonus_numerator * boost
    fuel_per_day = fuel // FUEL_WINDOW
    return fuel_per_day // SCALED_QUOTE_PRECISION

def calculate_insurance_fuel_bonus(
    spot_market: SpotMarketAccount,
    token_stake_amount: int,
    fuel_bonus_numerator: int
) -> int:
    """
    Calculate the insurance fuel bonus for a given spot market.

    Args:
        spot_market (SpotMarketAccount): The spot market account.
        token_stake_amount (int): The amount of tokens staked.
        fuel_bonus_numerator (int): The fuel bonus numerator.

    Returns:
        int: The calculated insurance fuel bonus.

    Raises:
        ValueError: If fuel_bonus_numerator is not positive.
    """
    if fuel_bonus_numerator <= 0:
        raise ValueError("fuel_bonus_numerator must be positive")
    
    return calculate_scaled_fuel(
        token_stake_amount,
        spot_market.fuel_boost_insurance,
        fuel_bonus_numerator
    )

def calculate_spot_fuel_bonus(
    spot_market: SpotMarketAccount,
    signed_token_value: int,
    fuel_bonus_numerator: int
) -> int:
    """
    Calculate the spot fuel bonus for a given spot market.

    Args:
        spot_market (SpotMarketAccount): The spot market account.
        signed_token_value (int): The signed token value.
        fuel_bonus_numerator (int): The fuel bonus numerator.

    Returns:
        int: The calculated spot fuel bonus.

    Raises:
        ValueError: If fuel_bonus_numerator is not positive.
    """
    if fuel_bonus_numerator <= 0:
        raise ValueError("fuel_bonus_numerator must be positive")

    if abs(signed_token_value) <= QUOTE_PRECISION:
        return 0
    
    boost = spot_market.fuel_boost_deposits if signed_token_value > 0 else spot_market.fuel_boost_borrows
    return calculate_scaled_fuel(signed_token_value, boost, fuel_bonus_numerator)

def calculate_perp_fuel_bonus(
    perp_market: PerpMarketAccount,
    base_asset_value: int,
    fuel_bonus_numerator: int
) -> int:
    """
    Calculate the perpetual fuel bonus for a given perpetual market.

    Args:
        perp_market (PerpMarketAccount): The perpetual market account.
        base_asset_value (int): The base asset value.
        fuel_bonus_numerator (int): The fuel bonus numerator.

    Returns:
        int: The calculated perpetual fuel bonus.

    Raises:
        ValueError: If fuel_bonus_numerator is not positive.
    """
    if fuel_bonus_numerator <= 0:
        raise ValueError("fuel_bonus_numerator must be positive")

    if abs(base_asset_value) <= QUOTE_PRECISION:
        return 0
    
    return calculate_scaled_fuel(
        base_asset_value,
        perp_market.fuel_boost_position,
        fuel_bonus_numerator
    )
