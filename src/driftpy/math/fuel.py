from driftpy.types import SpotMarketAccount, PerpMarketAccount
from driftpy.constants.numeric_constants import QUOTE_PRECISION, FUEL_WINDOW

def _calculate_fuel_bonus(
    value: int, 
    boost_factor: int, 
    bonus_numerator: int
) -> int:
    """Calculate fuel bonus using unified formula.
    
    Args:
        value: Absolute value of the position/stake
        boost_factor: Market-specific boost multiplier
        bonus_numerator: Protocol-level bonus parameter
        
    Returns:
        Daily fuel bonus scaled by QUOTE_PRECISION
    """
    if abs(value) <= QUOTE_PRECISION:  # Dust threshold
        return 0
        
    return (
        abs(value) 
        * bonus_numerator 
        * boost_factor 
    ) // (FUEL_WINDOW * (QUOTE_PRECISION // 10))  # Combined divisions


def calculate_insurance_fuel_bonus(
    spot_market: SpotMarketAccount, 
    token_stake_amount: int, 
    fuel_bonus_numerator: int
) -> int:
    """Calculate insurance fund fuel bonus.
    
    Args:
        spot_market: Spot market account data
        token_stake_amount: Staked token amount (absolute value)
        fuel_bonus_numerator: Protocol-level bonus parameter
        
    Returns:
        Scaled daily insurance fuel bonus
    """
    return _calculate_fuel_bonus(
        token_stake_amount,
        spot_market.fuel_boost_insurance,
        fuel_bonus_numerator
    )


def calculate_spot_fuel_bonus(
    spot_market: SpotMarketAccount, 
    signed_token_value: int, 
    fuel_bonus_numerator: int
) -> int:
    """Calculate spot market fuel bonus (deposits/borrows).
    
    Args:
        spot_market: Spot market account data
        signed_token_value: Signed position value 
            (positive for deposits, negative for borrows)
        fuel_bonus_numerator: Protocol-level bonus parameter
            
    Returns:
        Scaled daily fuel bonus based on position type
    """
    if signed_token_value == 0:
        return 0
        
    boost_factor = (
        spot_market.fuel_boost_deposits if signed_token_value > 0 
        else spot_market.fuel_boost_borrows
    )
    return _calculate_fuel_bonus(
        signed_token_value,
        boost_factor,
        fuel_bonus_numerator
    )


def calculate_perp_fuel_bonus(
    perp_market: PerpMarketAccount, 
    base_asset_value: int, 
    fuel_bonus_numerator: int
) -> int:
    """Calculate perp market position fuel bonus.
    
    Args:
        perp_market: Perp market account data
        base_asset_value: Absolute position size
        fuel_bonus_numerator: Protocol-level bonus parameter
        
    Returns:
        Scaled daily perp position fuel bonus
    """
    return _calculate_fuel_bonus(
        base_asset_value,
        perp_market.fuel_boost_position,
        fuel_bonus_numerator
    )
