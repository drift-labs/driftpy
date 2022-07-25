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

@dataclass
class StateAccount:
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
    order_auction_duration: int
    # upgrade-ability
    padding0: int
    padding1: int

# ---

@_rust_enum
class OracleSource:
    Pyth = constructor()
    Switchboard = constructor()
    QuoteAsset = constructor()

@_rust_enum
class DepositDirection:
    DEPOSIT = constructor()
    WITHDRAW = constructor()

@dataclass
class TradeDirection:
    long: Optional[Any]
    short: Optional[Any]

@_rust_enum
class OrderType:
    MARKET = constructor()
    LIMIT = constructor()
    TRIGGER_MARKET = constructor()
    TRIGGER_LIMIT = constructor()

@_rust_enum
class OrderStatus:
    INIT = constructor()
    OPEN = constructor()
    FILLED = constructor()
    CANCELED = constructor()

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

@_rust_enum
class OrderAction:
    PLACE = constructor()
    FILL = constructor()
    CANCEL = constructor()

@_rust_enum
class PositionDirection:
    LONG = constructor()
    SHORT = constructor()

@_rust_enum
class SwapDirection:
    ADD = constructor()
    REMOVE = constructor()

@_rust_enum
class AssetType:
    QUOTE = constructor()
    BASE = constructor()

@_rust_enum
class BankBalanceType:
    DEPOSIT = constructor()
    BORROW = constructor()

# --- 

@dataclass
class Order:
    status: OrderStatus
    order_type: OrderType
    ts: int
    order_id: int
    user_order_id: int
    market_index: int
    price: int
    user_base_asset_amount: int
    base_asset_amount: int
    base_asset_amount_filled: int
    quote_asset_amount: int
    quote_asset_amount_filled: int
    fee: int
    direction: PositionDirection
    reduce_only: bool
    trigger_price: int
    trigger_condition: OrderTriggerCondition
    discount_tier: OrderDiscountTier
    referrer: PublicKey
    post_only: bool
    immediate_or_cancel: bool
    oracle_price_offset: int

@dataclass
class OrderParamsOptionalAccounts:
    discount_token: bool = False
    referrer: bool = False

@dataclass
class OrderParams:
    # necessary 
    order_type: OrderType
    direction: PositionDirection
    market_index: int
    base_asset_amount: int
    # optional 
    user_order_id: int = 0 
    price: int = 0 
    reduce_only: bool = False
    post_only: bool = False
    immediate_or_cancel: bool = False
    trigger_price: int = 0 
    trigger_condition: OrderTriggerCondition = OrderTriggerCondition.ABOVE()
    position_limit: int = 0
    oracle_price_offset: int = 0
    auction_duration: int = 0
    padding0: bool = 0 
    padding1: bool = 0 
    optional_accounts: OrderParamsOptionalAccounts = OrderParamsOptionalAccounts()

@dataclass
class MakerInfo:
    maker: PublicKey
    order: Order

@dataclass
class OrderFillerRewardStructure:
    reward_numerator: int
    reward_denominator: int
    time_based_reward_lower_bound: int  # minimum time filler reward

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
    unsettled_pnl: int
    open_bids: int
    open_asks: int

    # lp stuff
    lp_shares: int
    lp_base_asset_amount: int
    lp_quote_asset_amount: int
    last_cumulative_funding_payment_per_lp: int
    last_cumulative_fee_per_lp: int
    last_cumulative_net_base_asset_amount_per_lp: int
    last_lp_add_time: int

    # upgrade-ability
    padding0: int
    padding1: int
    padding2: int
    padding3: int
    padding4: int

    ## dw why this doesnt register :(
    # def is_available(self): 
    #     return self.base_asset_amount == 0 and self.open_orders == 0 and self.lp_shares == 0

@dataclass
class UserFees:
    total_fee_paid: int
    total_fee_rebate: int
    total_token_discount: int
    total_referral_reward: int
    total_referee_discount: int

@dataclass
class UserBankBalance:
    bank_index: int
    balance_type: BankBalanceType
    balance: int


@dataclass
class User:
    authority: PublicKey
    user_id: int
    name: list[int]
    bank_balances: list[UserBankBalance]
    fees: UserFees
    next_order_id: int
    positions: list[MarketPosition]
    orders: list[Order]

@dataclass
class PoolBalance:
    balance: int

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
    cumulative_deposit_interest: int
    cumulative_borrow_interest: int
    last_updated: int
    initial_asset_weight: int
    maintenance_asset_weight: int
    initial_liability_weight: int
    maintenance_liability_weight: int

@dataclass
class AMM:
    oracle: PublicKey
    oracle_source: OracleSource
    last_oracle_price: int
    last_oracle_conf_pct: int
    last_oracle_delay: int
    last_oracle_normalised_price: int
    last_oracle_price_twap: int
    last_oracle_price_twap_ts: int
    last_oracle_mark_spread_pct: int

    base_asset_reserve: int
    quote_asset_reserve: int
    sqrt_k: int
    peg_multiplier: int

    terminal_quote_asset_reserve: int
    net_base_asset_amount: int
    quote_asset_amount_long: int
    quote_asset_amount_short: int

    ## lp stuff
    cumulative_funding_payment_per_lp: int
    cumulative_fee_per_lp: int
    cumulative_net_base_asset_amount_per_lp: int
    lp_cooldown_time: int
    user_lp_shares: int

    ## funding
    last_funding_rate: int
    last_funding_rate_ts: int
    funding_period: int
    cumulative_funding_rate_long: int
    cumulative_funding_rate_short: int
    cumulative_repeg_rebate_long: int
    cumulative_repeg_rebate_short: int

    mark_std: int
    last_mark_price_twap: int
    last_mark_price_twap_ts: int

    ## trade constraints
    minimum_quote_asset_trade_size: int
    base_asset_amount_step_size: int

    ## market making
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

    ## fee tracking
    total_fee: int
    total_mm_fee: int
    total_exchange_fee: int
    total_fee_minus_distributions: int
    total_fee_withdrawn: int
    net_revenue_since_last_funding: int
    fee_pool: int
    last_update_slot: int

    padding0: int
    padding1: int
    padding2: int
    padding3: int

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
    margin_ratio_partial: int
    margin_ratio_maintenance: int
    next_fill_record_id: int
    next_funding_rate_record_id: int
    next_curve_record_id: int
    pnl_pool: PoolBalance
    unsettled_profit: int
    unsettled_loss: int

    padding0: int
    padding1: int
    padding2: int
    padding3: int
    padding4: int
