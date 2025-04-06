import math
from driftpy.constants.numeric_constants import *
from driftpy.types import OraclePriceData, AMM
from driftpy.math.amm import calculate_peg_from_target_price, calculate_price

def calculate_optimal_peg_and_budget(
    amm: AMM, 
    oracle_price_data: OraclePriceData
) -> tuple[int, int, int, bool]:
    """Calculate optimal peg multiplier and budget for AMM adjustment.
    
    Args:
        amm: AMM state object
        oracle_price_data: Current oracle price data
        
    Returns:
        tuple: (target_price, new_peg, budget, check_lower_bound)
    """
    reserve_price = calculate_price(
        amm.base_asset_reserve, 
        amm.quote_asset_reserve, 
        amm.peg_multiplier
    )
    target_price = oracle_price_data.price
    new_peg = calculate_peg_from_target_price(
        target_price, 
        amm.base_asset_reserve, 
        amm.quote_asset_reserve
    )
    
    pre_peg_cost = calculate_repeg_cost(amm, new_peg)
    budget = max(0, amm.total_fee_minus_distributions - (amm.total_exchange_fee // 2))
    
    check_lower_bound = True
    if budget >= pre_peg_cost:
        return (target_price, new_peg, budget, check_lower_bound)
        
    # Handle budget constraint
    half_spread = (amm.max_spread * target_price) // (2 * BID_ASK_SPREAD_PRECISION)
    price_gap = reserve_price - target_price
    
    if abs(price_gap) > half_spread:
        mark_adj = abs(price_gap) - half_spread
        new_target = reserve_price + (-mark_adj if price_gap < 0 else mark_adj)
        new_peg = calculate_peg_from_target_price(
            new_target, 
            amm.base_asset_reserve, 
            amm.quote_asset_reserve
        )
        return (new_target, new_peg, calculate_repeg_cost(amm, new_peg), False)

    check_lower_bound = amm.total_fee_minus_distributions >= (amm.total_exchange_fee // 2)
    return (target_price, new_peg, budget, check_lower_bound)

def calculate_repeg_cost(amm: AMM, new_peg: int) -> int:
    """Calculate cost of adjusting peg multiplier."""
    dqar = amm.quote_asset_reserve - amm.terminal_quote_asset_reserve
    cost = (dqar * (new_peg - amm.peg_multiplier)) // (AMM_TO_QUOTE_PRECISION_RATIO * PEG_PRECISION)
    return math.floor(cost)

def calculate_k_cost(market: AMM, p: float) -> float:
    """Calculate cost function for adjusting AMM curvature."""
    x = market.base_asset_reserve / AMM_RESERVE_PRECISION
    y = market.quote_asset_reserve / AMM_RESERVE_PRECISION
    d = market.base_asset_amount / AMM_RESERVE_PRECISION
    Q = market.peg_multiplier / PEG_PRECISION
    
    return -((1/(x + d) - p/(x*p + d)) * y * d * Q

def calculate_budgeted_k(market: AMM, cost: float) -> float:
    """Calculate curvature parameter within budget constraints."""
    x = market.base_asset_reserve / AMM_RESERVE_PRECISION
    y = market.quote_asset_reserve / AMM_RESERVE_PRECISION
    d = market.base_asset_amount / AMM_RESERVE_PRECISION
    Q = market.peg_multiplier / PEG_PRECISION
    
    numerator = y * d**2 * Q - cost * d * (x + d)
    denominator = cost * x * (x + d) + y * d**2 * Q
    return numerator / denominator

def calculate_budgeted_peg(amm: AMM, budget: int, target_price: int) -> int:
    """Calculate maximum affordable peg adjustment within budget."""
    dqar = amm.quote_asset_reserve - amm.terminal_quote_asset_reserve
    per_peg_cost = dqar // (AMM_RESERVE_PRECISION // PRICE_PRECISION)
    
    if per_peg_cost != 0:
        per_peg_cost += 1 if per_peg_cost > 0 else -1
    
    target_peg = (target_price * amm.base_asset_reserve) // (amm.quote_asset_reserve * PRICE_DIV_PEG)
    peg_direction = target_peg - amm.peg_multiplier
    
    if (per_peg_cost * peg_direction) < 0:  # Opposite signs
        return target_peg
    
    return max(1, amm.peg_multiplier + (budget * PEG_PRECISION) // per_peg_cost)

def calculate_adjust_k_cost(
    amm: AMM, 
    numerator: int, 
    denominator: int
) -> int:
    """Calculate cost of adjusting AMM curvature parameter K."""
    x = amm.base_asset_reserve
    y = amm.quote_asset_reserve
    d = amm.base_asset_amount_with_amm
    Q = amm.peg_multiplier
    p = (numerator * PRICE_PRECISION) // denominator
    
    quote_scale = (y * d * Q) // AMM_RESERVE_PRECISION
    base_term = (x + d)
    price_term = (x * p) // PRICE_PRECISION + d
    
    cost = (
        (quote_scale // base_term) - 
        ((quote_scale * p) // (price_term * PRICE_PRECISION))
    ) // (PERCENTAGE_PRECISION**2 * AMM_TO_QUOTE_PRECISION_RATIO * PEG_PRECISION)
    
    return -cost
