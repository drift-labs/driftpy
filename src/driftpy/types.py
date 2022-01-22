from dataclasses import dataclass
from solana.publickey import PublicKey


@dataclass
class PriceDivergence:
    mark_oracle_divergence_numerator: int
    mark_oracle_divergence_denominator: int


@dataclass
class Validity:
    slots_before_stale: int
    confidence_interval_max_size: int
    too_volatile_ratio: int


@dataclass
class OracleGuardRails:
    price_divergence: PriceDivergence
    validity: Validity
    use_for_liquidations: bool


@dataclass
class DiscountTokenTier:
    minimum_balance: int
    discount_numerator: int
    discount_denominator: int


@dataclass
class DiscountTokenTiers:
    first_tier: DiscountTokenTier
    second_tier: DiscountTokenTier
    third_tier: DiscountTokenTier
    fourth_tier: DiscountTokenTier


@dataclass
class ReferralDiscount:
    referrer_reward_numerator: int
    referrer_reward_denominator: int
    referee_discount_numerator: int
    referee_discount_denominator: int


@dataclass
class FeeStructure:
    fee_numerator: int
    fee_denominator: int
    discount_token_tiers: DiscountTokenTiers
    referral_discount: ReferralDiscount


@dataclass
class StateAccount:
    admin: PublicKey
    funding_paused: bool
    exchange_paused: bool
    admin_controls_prices: bool
    collateral_mint: PublicKey
    collateral_vault: PublicKey
    collateral_vault_authority: PublicKey
    collateral_vault_nonce: int
    insurance_vault: PublicKey
    insurance_vault_authority: PublicKey
    insurance_vault_nonce: int
    margin_ratio_initial: int
    margin_ratio_maintenance: int
    margin_ratio_partial: int
    markets: PublicKey
    curve_history: PublicKey
    deposit_history: PublicKey
    funding_rate_history: PublicKey
    funding_payment_history: PublicKey
    trade_history: PublicKey
    liquidation_history: PublicKey
    partial_liquidation_close_percentage_numerator: int
    partial_liquidation_close_percentage_denominator: int
    partial_liquidation_penalty_percentage_numerator: int
    partial_liquidation_penalty_percentage_denominator: int
    full_liquidation_penalty_percentage_numerator: int
    full_liquidation_penalty_percentage_denominator: int
    partial_liquidation_liquidator_share_denominator: int
    full_liquidation_liquidator_share_denominator: int
    fee_structure: FeeStructure
    total_fee: int
    total_fee_withdrawn: int
    whitelist_mint: PublicKey
    discount_mint: PublicKey
    oracle_guard_rails: OracleGuardRails
    max_deposit: int
