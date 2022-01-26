from typing import Optional, Any
from dataclasses import dataclass
from sumtypes import constructor  # type: ignore
from borsh_construct.enum import _rust_enum
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


@_rust_enum
class OracleSource:
    Pyth = constructor()
    Switchboard = constructor()


@dataclass
class AMM:
    base_asset_reserve: int
    sqrt_k: int
    cumulative_funding_rate: int
    last_funding_rate: int
    last_funding_rate_ts: int
    last_mark_price_twap: int
    last_mark_price_twap_ts: int
    last_oracle_price_twap: int
    last_oracle_price_twap_ts: int
    oracle: PublicKey
    oracle_source: OracleSource
    funding_period: int
    quote_asset_reserve: int
    peg_multiplier: int
    cumulative_funding_rate_long: int
    cumulative_funding_rate_short: int
    cumulative_repeg_rebate_long: int
    cumulative_repeg_rebate_short: int
    total_fee_minus_distributions: int
    total_fee_withdrawn: int
    total_fee: int
    minimum_trade_size: int


@dataclass
class Market:
    amm: AMM
    base_asset_amount: int
    base_asset_amount_long: int
    base_asset_amount_short: int
    initialized: bool
    open_interest: int


@dataclass
class MarketsAccount:
    account_index: int
    markets: list[Market]


# ClearingHouse Account Types


@_rust_enum
class DepositDirection:
    DEPOSIT = constructor()
    WITHDRAW = constructor()


@dataclass
class DepositRecord:
    ts: int
    record_id: int
    user_authority: PublicKey
    user: PublicKey
    direction: DepositDirection
    collateral_before: int
    cumulative_deposits_before: int
    amount: int


@dataclass
class CurveRecord:
    ts: int
    record_id: int
    market_index: int
    peg_multiplier_before: int
    base_asset_reserve_before: int
    quote_asset_reserve_before: int
    sqrt_k_before: int
    peg_multiplier_after: int
    base_asset_reserve_after: int
    quote_asset_reserve_after: int
    sqrt_k_after: int
    base_asset_amount_long: int
    base_asset_amount_short: int
    base_asset_amount: int
    open_interest: int


@dataclass
class TradeDirection:
    long: Optional[Any]
    short: Optional[Any]


@dataclass
class TradeRecord:
    ts: int
    record_id: int
    user_authority: PublicKey
    user: PublicKey
    direction: TradeDirection
    base_asset_amount: int
    quote_asset_amount: int
    mark_price_before: int
    mark_price_after: int
    fee: int
    referrer_reward: int
    referee_discount: int
    token_discount: int
    market_index: int
    liquidation: bool
    oracle_price: int


@dataclass
class FundingRateRecord:
    ts: int
    record_id: int
    market_index: int
    funding_rate: int
    cumulative_funding_rate_long: int
    cumulative_funding_rate_short: int
    oracle_price_twap: int
    mark_price_twap: int


@dataclass
class FundingPaymentRecord:
    ts: int
    record_id: int
    user_authority: PublicKey
    user: PublicKey
    market_index: int
    funding_payment: int
    base_asset_amount: int
    user_last_cumulative_funding: int
    user_last_funding_rate_ts: int
    amm_cumulative_funding_long: int
    amm_cumulative_funding_short: int


@dataclass
class LiquidationRecord:
    ts: int
    record_id: int
    user_authority: PublicKey
    user: PublicKey
    partial: bool
    base_asset_value: int
    base_asset_value_closed: int
    liquidation_fee: int
    fee_to_liquidator: int
    fee_to_insurance_fund: int
    liquidator: PublicKey
    total_collateral: int
    collateral: int
    unrealized_pnl: int
    margin_ratio: int


@dataclass
class TradeHistoryAccount:
    head: int
    trade_records: list[TradeRecord]


@dataclass
class DepositHistoryAccount:
    head: int
    deposit_records: list[DepositRecord]


@dataclass
class CurveHistoryAccount:
    head: int
    curve_records: list[CurveRecord]


@dataclass
class FundingRateHistoryAccount:
    head: int
    funding_rate_records: list[FundingRateRecord]


@dataclass
class FundingPaymentHistoryAccount:
    head: int
    funding_payment_records: list[FundingPaymentRecord]


@dataclass
class LiquidationHistoryAccount:
    head: int
    liquidation_records: list[LiquidationRecord]


@dataclass
class User:
    authority: PublicKey
    collateral: int
    cumulative_deposits: int
    total_fee_paid: int
    total_token_discount: int
    total_referral_reward: int
    total_referee_discount: int
    positions: PublicKey
    # upgrade-ability
    padding0: int
    padding1: int
    padding2: int
    padding3: int


@dataclass
class MarketPosition:
    market_index: int
    base_asset_amount: int
    quote_asset_amount: int
    last_cumulative_funding_rate: int
    last_cumulative_repeg_rebate: int
    last_funding_rate_ts: int
    stop_loss_price: int
    stop_loss_amount: int
    stop_profit_price: int
    stop_profit_amount: int
    transfer_to: PublicKey
    # upgrade-ability
    padding0: int
    padding1: int


@dataclass
class UserPositions:
    user: PublicKey
    positions: tuple[
        MarketPosition, MarketPosition, MarketPosition, MarketPosition, MarketPosition
    ]


@_rust_enum
class PositionDirection:
    LONG = constructor()
    SHORT = constructor()
