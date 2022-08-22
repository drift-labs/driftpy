from dataclasses import dataclass
from solana.publickey import PublicKey
from borsh_construct.enum import _rust_enum
from sumtypes import constructor

@_rust_enum
class SwapDirection:
    ADD = constructor()
    REMOVE = constructor()
 
@_rust_enum
class PositionDirection:
    LONG = constructor()
    SHORT = constructor()
 
@_rust_enum
class TwapPeriod:
    FUNDING_PERIOD = constructor()
    FIVE_MIN = constructor()
 
@_rust_enum
class LiquidationMultiplierType:
    DISCOUNT = constructor()
    PREMIUM = constructor()
 
@_rust_enum
class MarginRequirementType:
    INITIAL = constructor()
    MAINTENANCE = constructor()
 
@_rust_enum
class PositionUpdateType:
    OPEN = constructor()
    INCREASE = constructor()
    REDUCE = constructor()
    CLOSE = constructor()
    FLIP = constructor()
 
@_rust_enum
class BankBalanceType:
    DEPOSIT = constructor()
    BORROW = constructor()
 
@_rust_enum
class DepositDirection:
    D_E_P_O_S_I_T = constructor()
    W_I_T_H_D_R_A_W = constructor()
 
@_rust_enum
class OrderAction:
    PLACE = constructor()
    CANCEL = constructor()
    FILL = constructor()
    TRIGGER = constructor()
    EXPIRE = constructor()
 
@_rust_enum
class OrderActionExplanation:
    NONE = constructor()
    BREACHED_MARGIN_REQUIREMENT = constructor()
    ORACLE_PRICE_BREACHED_LIMIT_PRICE = constructor()
    MARKET_ORDER_FILLED_TO_LIMIT_PRICE = constructor()
    MARKET_ORDER_AUCTION_EXPIRED = constructor()
    CANCELED_FOR_LIQUIDATION = constructor()
    ORDER_FILLED_WITH_A_M_M = constructor()
    ORDER_FILLED_WITH_MATCH = constructor()
 
@_rust_enum
class LiquidationType:
    LIQUIDATE_PERP = constructor()
    LIQUIDATE_BORROW = constructor()
    LIQUIDATE_BORROW_FOR_PERP_PNL = constructor()
    LIQUIDATE_PERP_PNL_FOR_DEPOSIT = constructor()
    PERP_BANKRUPTCY = constructor()
    BORROW_BANKRUPTCY = constructor()
 
@_rust_enum
class FulfillmentMethod:
    A_M_M = constructor()
    MATCH = constructor()
 
@_rust_enum
class OracleSource:
    PYTH = constructor()
    SWITCHBOARD = constructor()
    QUOTE_ASSET = constructor()
 
@_rust_enum
class OrderStatus:
    INIT = constructor()
    OPEN = constructor()
    FILLED = constructor()
    CANCELED = constructor()
 
@_rust_enum
class OrderType:
    MARKET = constructor()
    LIMIT = constructor()
    TRIGGER_MARKET = constructor()
    TRIGGER_LIMIT = constructor()
 
@_rust_enum
class OrderDiscountTier:
    NONE = constructor()
    FIRST = constructor()
    SECOND = constructor()
    THIRD = constructor()
    FOURTH = constructor()
 
@_rust_enum
class OrderTriggerCondition:
    ABOVE = constructor()
    BELOW = constructor()
 
@dataclass
class OrderParamsOptionalAccounts:
    discount_token: bool
    referrer: bool
 
@dataclass
class OrderParams:
    order_type: OrderType
    direction: PositionDirection
    user_order_id: int
    base_asset_amount: int
    price: int
    market_index: int
    reduce_only: bool
    post_only: bool
    immediate_or_cancel: bool
    trigger_price: int
    trigger_condition: OrderTriggerCondition
    optional_accounts: OrderParamsOptionalAccounts
    position_limit: int
    oracle_price_offset: int
    auction_duration: int
    padding0: bool
    padding1: bool
 
@dataclass
class MarketPosition:
    market_index: int
    base_asset_amount: int
    quote_asset_amount: int
    quote_entry_amount: int
    last_cumulative_funding_rate: int
    last_cumulative_repeg_rebate: int
    last_funding_rate_ts: int
    open_orders: int
    open_bids: int
    open_asks: int
    realized_pnl: int
    lp_shares: int
    last_net_base_asset_amount_per_lp: int
    last_net_quote_asset_amount_per_lp: int
    last_lp_add_time: int
    padding0: int
    padding1: int
    padding2: int
    padding3: int
    padding4: int
 
@dataclass
class PoolBalance:
    balance: int
 
@dataclass
class AMM:
    oracle: PublicKey
    oracle_source: OracleSource
    last_oracle_price: int
    last_oracle_conf_pct: int
    last_oracle_delay: int
    last_oracle_normalised_price: int
    last_oracle_price_twap: int
    last_oracle_price_twap5min: int
    last_oracle_price_twap_ts: int
    last_oracle_mark_spread_pct: int
    base_asset_reserve: int
    quote_asset_reserve: int
    min_base_asset_reserve: int
    max_base_asset_reserve: int
    sqrt_k: int
    peg_multiplier: int
    terminal_quote_asset_reserve: int
    net_base_asset_amount: int
    quote_asset_amount_long: int
    quote_asset_amount_short: int
    quote_entry_amount_long: int
    quote_entry_amount_short: int
    net_unsettled_lp_base_asset_amount: int
    lp_cooldown_time: int
    user_lp_shares: int
    market_position_per_lp: MarketPosition
    last_funding_rate: int
    last_funding_rate_long: int
    last_funding_rate_short: int
    last_funding_rate_ts: int
    funding_period: int
    cumulative_funding_rate_long: int
    cumulative_funding_rate_short: int
    cumulative_repeg_rebate_long: int
    cumulative_repeg_rebate_short: int
    mark_std: int
    last_mark_price_twap: int
    last_mark_price_twap5min: int
    last_mark_price_twap_ts: int
    minimum_quote_asset_trade_size: int
    max_base_asset_amount_ratio: int
    max_slippage_ratio: int
    base_asset_amount_step_size: int
    market_position: MarketPosition
    base_spread: int
    long_spread: int
    short_spread: int
    max_spread: int
    ask_base_asset_reserve: int
    ask_quote_asset_reserve: int
    bid_base_asset_reserve: int
    bid_quote_asset_reserve: int
    last_bid_price_twap: int
    last_ask_price_twap: int
    long_intensity_count: int
    long_intensity_volume: int
    short_intensity_count: int
    short_intensity_volume: int
    curve_update_intensity: int
    total_fee: int
    total_mm_fee: int
    total_exchange_fee: int
    total_fee_minus_distributions: int
    total_fee_withdrawn: int
    net_revenue_since_last_funding: int
    fee_pool: PoolBalance
    last_update_slot: int
    last_oracle_valid: bool
    padding0: int
    padding1: int
    padding2: int
    padding3: int
 
@dataclass
class PriceDivergenceGuardRails:
    mark_oracle_divergence_numerator: int
    mark_oracle_divergence_denominator: int
 
@dataclass
class ValidityGuardRails:
    slots_before_stale: int
    confidence_interval_max_size: int
    too_volatile_ratio: int
 
@dataclass
class OracleGuardRails:
    price_divergence: PriceDivergenceGuardRails
    validity: ValidityGuardRails
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
class OrderFillerRewardStructure:
    reward_numerator: int
    reward_denominator: int
    time_based_reward_lower_bound: int
 
@dataclass
class FeeStructure:
    fee_numerator: int
    fee_denominator: int
    discount_token_tiers: DiscountTokenTiers
    referral_discount: ReferralDiscount
    maker_rebate_numerator: int
    maker_rebate_denominator: int
    filler_reward_structure: OrderFillerRewardStructure
    cancel_order_fee: int
 
@dataclass
class DiscountTokenTiers:
    first_tier: DiscountTokenTier
    second_tier: DiscountTokenTier
    third_tier: DiscountTokenTier
    fourth_tier: DiscountTokenTier
 
@dataclass
class UserBankBalance:
    bank_index: int
    balance_type: BankBalanceType
    balance: int
 
@dataclass
class Order:
    status: OrderStatus
    order_type: OrderType
    ts: int
    slot: int
    order_id: int
    user_order_id: int
    market_index: int
    price: int
    existing_position_direction: PositionDirection
    base_asset_amount: int
    base_asset_amount_filled: int
    quote_asset_amount_filled: int
    fee: int
    direction: PositionDirection
    reduce_only: bool
    post_only: bool
    immediate_or_cancel: bool
    discount_tier: OrderDiscountTier
    trigger_price: int
    trigger_condition: OrderTriggerCondition
    triggered: bool
    referrer: PublicKey
    oracle_price_offset: int
    auction_start_price: int
    auction_end_price: int
    auction_duration: int
    padding: list[int]
 
@dataclass
class Bank:
    bank_index: int
    pubkey: PublicKey
    oracle: PublicKey
    oracle_source: OracleSource
    mint: PublicKey
    vault: PublicKey
    vault_authority: PublicKey
    vault_authority_nonce: int
    decimals: int
    optimal_utilization: int
    optimal_borrow_rate: int
    max_borrow_rate: int
    deposit_balance: int
    borrow_balance: int
    deposit_token_twap: int
    borrow_token_twap: int
    utilization_twap: int
    cumulative_deposit_interest: int
    cumulative_borrow_interest: int
    last_interest_ts: int
    last_twap_ts: int
    initial_asset_weight: int
    maintenance_asset_weight: int
    initial_liability_weight: int
    maintenance_liability_weight: int
    imf_factor: int
    liquidation_fee: int
    withdraw_guard_threshold: int
 
@dataclass
class Market:
    market_index: int
    pubkey: PublicKey
    initialized: bool
    amm: AMM
    base_asset_amount_long: int
    base_asset_amount_short: int
    open_interest: int
    margin_ratio_initial: int
    margin_ratio_maintenance: int
    next_fill_record_id: int
    next_funding_rate_record_id: int
    next_curve_record_id: int
    pnl_pool: PoolBalance
    imf_factor: int
    unsettled_initial_asset_weight: int
    unsettled_maintenance_asset_weight: int
    unsettled_imf_factor: int
    liquidation_fee: int
    padding0: int
    padding1: int
    padding2: int
    padding3: int
    padding4: int
 
@dataclass
class State:
    admin: PublicKey
    exchange_paused: bool
    funding_paused: bool
    admin_controls_prices: bool
    insurance_vault: PublicKey
    insurance_vault_authority: PublicKey
    insurance_vault_nonce: int
    margin_ratio_initial: int
    margin_ratio_maintenance: int
    margin_ratio_partial: int
    partial_liquidation_close_percentage_numerator: int
    partial_liquidation_close_percentage_denominator: int
    partial_liquidation_penalty_percentage_numerator: int
    partial_liquidation_penalty_percentage_denominator: int
    full_liquidation_penalty_percentage_numerator: int
    full_liquidation_penalty_percentage_denominator: int
    partial_liquidation_liquidator_share_denominator: int
    full_liquidation_liquidator_share_denominator: int
    fee_structure: FeeStructure
    whitelist_mint: PublicKey
    discount_mint: PublicKey
    oracle_guard_rails: OracleGuardRails
    number_of_markets: int
    number_of_banks: int
    min_order_quote_asset_amount: int
    min_auction_duration: int
    max_auction_duration: int
    liquidation_margin_buffer_ratio: int
    padding0: int
    padding1: int
 
@dataclass
class User:
    authority: PublicKey
    user_id: int
    name: list[int]
    bank_balances: list[UserBankBalance]
    next_order_id: int
    positions: list[MarketPosition]
    orders: list[Order]
    next_liquidation_id: int
    being_liquidated: bool
    bankrupt: bool
 
@dataclass
class UserFees:
    total_fee_paid: int
    total_lp_fees: int
    total_fee_rebate: int
    total_token_discount: int
    total_referral_reward: int
    total_referee_discount: int
 
@dataclass
class UserStats:
    authority: PublicKey
    number_of_users: int
    referrer: PublicKey
    fees: UserFees
    maker_volume30d: int
    taker_volume30d: int
    filler_volume30d: int
    last_maker_volume30d_ts: int
    last_taker_volume30d_ts: int
    last_filler_volume30d_ts: int
 
