from driftpy.types import is_variant, PerpMarketAccount, SpotMarketAccount


def get_perp_market_tier_number(perp_market: PerpMarketAccount) -> int:
    if str(perp_market.contract_tier) == "ContractTier.A()":
        return 0
    elif str(perp_market.contract_tier) == "ContractTier.B()":
        return 1
    elif str(perp_market.contract_tier) == "ContractTier.C()":
        return 2
    elif str(perp_market.contract_tier) == "ContractTier.Speculative()":
        return 3
    elif str(perp_market.contract_tier) == "ContractTier.Isolated()":
        return 4
    else:
        return 5


def get_spot_market_tier_number(spot_market: SpotMarketAccount) -> int:
    if is_variant(spot_market.asset_tier, "COLLATERAL"):
        return 0
    elif is_variant(spot_market.asset_tier, "PROTECTED"):
        return 1
    elif is_variant(spot_market.asset_tier, "CROSS"):
        return 2
    elif is_variant(spot_market.asset_tier, "ISOLATED"):
        return 3
    elif is_variant(spot_market.asset_tier, "UNLISTED"):
        return 4
    else:
        return 5


def perp_tier_is_as_safe_as(
    perp_tier: int, other_perp_tier: int, other_spot_tier: int
) -> bool:
    as_safe_as_perp = perp_tier <= other_perp_tier
    as_safe_as_spot = other_spot_tier == 4 or (other_spot_tier >= 2 and perp_tier <= 2)
    return as_safe_as_perp and as_safe_as_spot
