from dataclasses import dataclass
from solana.publickey import PublicKey
from borsh_construct.enum import _rust_enum
from sumtypes import constructor
from typing import Optional

@_rust_enum
class SwapDirection:
    ADD = constructor()
    REMOVE = constructor()
 
@_rust_enum
class PositionDirection:
    LONG = constructor()
    SHORT = constructor()
 
@_rust_enum
class SpotFulfillmentType:
    SERUM_V3 = constructor()
    NONE = constructor()
 
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
class OracleValidity:
    INVALID = constructor()
    TOO_VOLATILE = constructor()
    TOO_UNCERTAIN = constructor()
    STALE_FOR_MARGIN = constructor()
    INSUFFICIENT_DATA_POINTS = constructor()
    STALE_FOR_A_M_M = constructor()
    VALID = constructor()
 
@_rust_enum
class DriftAction:
    UPDATE_FUNDING = constructor()
    SETTLE_PNL = constructor()
    TRIGGER_ORDER = constructor()
    FILL_ORDER_MATCH = constructor()
    FILL_ORDER_AMM = constructor()
    LIQUIDATE = constructor()
    MARGIN_CALC = constructor()
    UPDATE_TWAP = constructor()
    UPDATE_A_M_M_CURVE = constructor()
 
@_rust_enum
class PositionUpdateType:
    OPEN = constructor()
    INCREASE = constructor()
    REDUCE = constructor()
    CLOSE = constructor()
    FLIP = constructor()
 
@_rust_enum
class DepositExplanation:
    NONE = constructor()
    TRANSFER = constructor()
 
@_rust_enum
class DepositDirection:
    DEPOSIT = constructor()
    WITHDRAW = constructor()
 
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
    INSUFFICIENT_FREE_COLLATERAL = constructor()
    ORACLE_PRICE_BREACHED_LIMIT_PRICE = constructor()
    MARKET_ORDER_FILLED_TO_LIMIT_PRICE = constructor()
    ORDER_EXPIRED = constructor()
    LIQUIDATION = constructor()
    ORDER_FILLED_WITH_A_M_M = constructor()
    ORDER_FILLED_WITH_A_M_M_JIT = constructor()
    ORDER_FILLED_WITH_MATCH = constructor()
    ORDER_FILLED_WITH_MATCH_JIT = constructor()
    MARKET_EXPIRED = constructor()
    RISKING_INCREASING_ORDER = constructor()
    REDUCE_ONLY_ORDER_INCREASED_POSITION = constructor()
    ORDER_FILL_WITH_SERUM = constructor()
    NO_BORROW_LIQUIDITY = constructor()
 
@_rust_enum
class LPAction:
    ADD_LIQUIDITY = constructor()
    REMOVE_LIQUIDITY = constructor()
    SETTLE_LIQUIDITY = constructor()
 
@_rust_enum
class LiquidationType:
    LIQUIDATE_PERP = constructor()
    LIQUIDATE_SPOT = constructor()
    LIQUIDATE_BORROW_FOR_PERP_PNL = constructor()
    LIQUIDATE_PERP_PNL_FOR_DEPOSIT = constructor()
    PERP_BANKRUPTCY = constructor()
    SPOT_BANKRUPTCY = constructor()
 
@_rust_enum
class SettlePnlExplanation:
    NONE = constructor()
    EXPIRED_POSITION = constructor()
 
@_rust_enum
class StakeAction:
    STAKE = constructor()
    UNSTAKE_REQUEST = constructor()
    UNSTAKE_CANCEL_REQUEST = constructor()
    UNSTAKE = constructor()
 
@_rust_enum
class PerpFulfillmentMethod:
    A_M_M = constructor()
    MATCH = constructor()
 
@_rust_enum
class SpotFulfillmentMethod:
    SERUM_V3 = constructor()
    MATCH = constructor()
 
@_rust_enum
class OracleSource:
    PYTH = constructor()
    SWITCHBOARD = constructor()
    QUOTE_ASSET = constructor()
    PYTH_1K = constructor()
    PYTH_1M = constructor()
    
 
@_rust_enum
class MarketStatus:
    INITIALIZED = constructor()
    ACTIVE = constructor()
    FUNDING_PAUSED = constructor()
    AMM_PAUSED = constructor()
    FILL_PAUSED = constructor()
    WITHDRAW_PAUSED = constructor()
    REDUCE_ONLY = constructor()
    SETTLEMENT = constructor()
    DELISTED = constructor()
 
@_rust_enum
class ContractType:
    PERPETUAL = constructor()
    FUTURE = constructor()
 
@_rust_enum
class ContractTier:
    A = constructor()
    B = constructor()
    C = constructor()
    SPECULATIVE = constructor()
    ISOLATED = constructor()
 
@_rust_enum
class SpotBalanceType:
    DEPOSIT = constructor()
    BORROW = constructor()
 
@_rust_enum
class SpotFulfillmentConfigStatus:
    ENABLED = constructor()
    DISABLED = constructor()
 
@_rust_enum
class AssetTier:
    COLLATERAL = constructor()
    PROTECTED = constructor()
    CROSS = constructor()
    ISOLATED = constructor()
    UNLISTED = constructor()
 
@_rust_enum
class ExchangeStatus:
    ACTIVE = constructor()
    FUNDING_PAUSED = constructor()
    AMM_PAUSED = constructor()
    FILL_PAUSED = constructor()
    LIQ_PAUSED = constructor()
    WITHDRAW_PAUSED = constructor()
    PAUSED = constructor()
 
@_rust_enum
class UserStatus:
    ACTIVE = constructor()
    BEING_LIQUIDATED = constructor()
    BANKRUPT = constructor()
 
@_rust_enum
class AssetType:
    BASE = constructor()
    QUOTE = constructor()
 
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
    ORACLE = constructor()
 
@_rust_enum
class OrderTriggerCondition:
    ABOVE = constructor()
    BELOW = constructor()
    TRIGGERED_ABOVE = constructor()
    TRIGGERED_BELOW = constructor()
 
@_rust_enum
class MarketType:
    SPOT = constructor()
    PERP = constructor()
 
@dataclass
class OrderParams:
    order_type: OrderType
    market_type: MarketType
    direction: PositionDirection
    user_order_id: int
    base_asset_amount: int
    price: int
    market_index: int
    reduce_only: bool
    post_only: bool
    immediate_or_cancel: bool
    max_ts: Optional[int]
    trigger_price: Optional[int]
    trigger_condition: OrderTriggerCondition
    oracle_price_offset: Optional[int]
    auction_duration: Optional[int]
    auction_start_price: Optional[int]
    auction_end_price: Optional[int]
 
@dataclass
class HistoricalOracleData:
    last_oracle_price: int
    last_oracle_conf: int
    last_oracle_delay: int
    last_oracle_price_twap: int
    last_oracle_price_twap5min: int
    last_oracle_price_twap_ts: int
 
@dataclass
class PoolBalance:
    scaled_balance: int
    market_index: int
    padding: list[int]
 
@dataclass
class AMM:
    oracle: PublicKey
    historical_oracle_data: HistoricalOracleData
    base_asset_amount_per_lp: int
    quote_asset_amount_per_lp: int
    fee_pool: PoolBalance
    base_asset_reserve: int
    quote_asset_reserve: int
    concentration_coef: int
    min_base_asset_reserve: int
    max_base_asset_reserve: int
    sqrt_k: int
    peg_multiplier: int
    terminal_quote_asset_reserve: int
    base_asset_amount_long: int
    base_asset_amount_short: int
    base_asset_amount_with_amm: int
    base_asset_amount_with_unsettled_lp: int
    max_open_interest: int
    quote_asset_amount: int
    quote_entry_amount_long: int
    quote_entry_amount_short: int
    quote_break_even_amount_long: int
    quote_break_even_amount_short: int
    user_lp_shares: int
    last_funding_rate: int
    last_funding_rate_long: int
    last_funding_rate_short: int
    last24h_avg_funding_rate: int
    total_fee: int
    total_mm_fee: int
    total_exchange_fee: int
    total_fee_minus_distributions: int
    total_fee_withdrawn: int
    total_liquidation_fee: int
    cumulative_funding_rate_long: int
    cumulative_funding_rate_short: int
    total_social_loss: int
    ask_base_asset_reserve: int
    ask_quote_asset_reserve: int
    bid_base_asset_reserve: int
    bid_quote_asset_reserve: int
    last_oracle_normalised_price: int
    last_oracle_reserve_price_spread_pct: int
    last_bid_price_twap: int
    last_ask_price_twap: int
    last_mark_price_twap: int
    last_mark_price_twap5min: int
    last_update_slot: int
    last_oracle_conf_pct: int
    net_revenue_since_last_funding: int
    last_funding_rate_ts: int
    funding_period: int
    order_step_size: int
    order_tick_size: int
    min_order_size: int
    max_position_size: int
    volume24h: int
    long_intensity_volume: int
    short_intensity_volume: int
    last_trade_ts: int
    mark_std: int
    oracle_std: int
    last_mark_price_twap_ts: int
    base_spread: int
    max_spread: int
    long_spread: int
    short_spread: int
    long_intensity_count: int
    short_intensity_count: int
    max_fill_reserve_fraction: int
    max_slippage_ratio: int
    curve_update_intensity: int
    amm_jit_intensity: int
    oracle_source: OracleSource
    last_oracle_valid: bool
    padding: list[int]
 
@dataclass
class PriceDivergenceGuardRails:
    mark_oracle_divergence_numerator: int
    mark_oracle_divergence_denominator: int
 
@dataclass
class ValidityGuardRails:
    slots_before_stale_for_amm: int
    slots_before_stale_for_margin: int
    confidence_interval_max_size: int
    too_volatile_ratio: int
 
@dataclass
class OracleGuardRails:
    price_divergence: PriceDivergenceGuardRails
    validity: ValidityGuardRails
 
@dataclass
class FeeTier:
    fee_numerator: int
    fee_denominator: int
    maker_rebate_numerator: int
    maker_rebate_denominator: int
    referrer_reward_numerator: int
    referrer_reward_denominator: int
    referee_fee_numerator: int
    referee_fee_denominator: int
 
@dataclass
class OrderFillerRewardStructure:
    reward_numerator: int
    reward_denominator: int
    time_based_reward_lower_bound: int
 
@dataclass
class FeeStructure:
    fee_tiers: list[FeeTier]
    filler_reward_structure: OrderFillerRewardStructure
    referrer_reward_epoch_upper_bound: int
    flat_filler_fee: int
 
@dataclass
class SpotPosition:
    scaled_balance: int
    open_bids: int
    open_asks: int
    cumulative_deposits: int
    market_index: int
    balance_type: SpotBalanceType
    open_orders: int
    padding: list[int]
 
@dataclass
class Order:
    slot: int
    price: int
    base_asset_amount: int
    base_asset_amount_filled: int
    quote_asset_amount_filled: int
    trigger_price: int
    auction_start_price: int
    auction_end_price: int
    max_ts: int
    oracle_price_offset: int
    order_id: int
    market_index: int
    status: OrderStatus
    order_type: OrderType
    market_type: MarketType
    user_order_id: int
    existing_position_direction: PositionDirection
    direction: PositionDirection
    reduce_only: bool
    post_only: bool
    immediate_or_cancel: bool
    trigger_condition: OrderTriggerCondition
    auction_duration: int
    padding: list[int]
 
@dataclass
class InsuranceClaim:
    revenue_withdraw_since_last_settle: int
    max_revenue_withdraw_per_period: int
    quote_max_insurance: int
    quote_settled_insurance: int
    last_revenue_withdraw_ts: int
 
@dataclass
class PerpMarket:
    pubkey: PublicKey
    amm: AMM
    pnl_pool: PoolBalance
    name: list[int]
    insurance_claim: InsuranceClaim
    unrealized_pnl_max_imbalance: int
    expiry_ts: int
    expiry_price: int
    next_fill_record_id: int
    next_funding_rate_record_id: int
    next_curve_record_id: int
    imf_factor: int
    unrealized_pnl_imf_factor: int
    liquidator_fee: int
    if_liquidation_fee: int
    margin_ratio_initial: int
    margin_ratio_maintenance: int
    unrealized_pnl_initial_asset_weight: int
    unrealized_pnl_maintenance_asset_weight: int
    number_of_users_with_base: int
    number_of_users: int
    market_index: int
    status: MarketStatus
    contract_type: ContractType
    contract_tier: ContractTier
    padding: list[int]
 
@dataclass
class HistoricalIndexData:
    last_index_bid_price: int
    last_index_ask_price: int
    last_index_price_twap: int
    last_index_price_twap5min: int
    last_index_price_twap_ts: int
 
@dataclass
class InsuranceFund:
    vault: PublicKey
    total_shares: int
    user_shares: int
    shares_base: int
    unstaking_period: int
    last_revenue_settle_ts: int
    revenue_settle_period: int
    total_factor: int
    user_factor: int
 
@dataclass
class SpotMarket:
    pubkey: PublicKey
    oracle: PublicKey
    mint: PublicKey
    vault: PublicKey
    name: list[int]
    historical_oracle_data: HistoricalOracleData
    historical_index_data: HistoricalIndexData
    revenue_pool: PoolBalance
    spot_fee_pool: PoolBalance
    insurance_fund: InsuranceFund
    total_spot_fee: int
    deposit_balance: int
    borrow_balance: int
    cumulative_deposit_interest: int
    cumulative_borrow_interest: int
    total_social_loss: int
    total_quote_social_loss: int
    withdraw_guard_threshold: int
    max_token_deposits: int
    deposit_token_twap: int
    borrow_token_twap: int
    utilization_twap: int
    last_interest_ts: int
    last_twap_ts: int
    expiry_ts: int
    order_step_size: int
    order_tick_size: int
    min_order_size: int
    max_position_size: int
    next_fill_record_id: int
    next_deposit_record_id: int
    initial_asset_weight: int
    maintenance_asset_weight: int
    initial_liability_weight: int
    maintenance_liability_weight: int
    imf_factor: int
    liquidator_fee: int
    if_liquidation_fee: int
    optimal_utilization: int
    optimal_borrow_rate: int
    max_borrow_rate: int
    decimals: int
    market_index: int
    orders_enabled: bool
    oracle_source: OracleSource
    status: MarketStatus
    asset_tier: AssetTier
    padding: list[int]
 
@dataclass
class SerumV3FulfillmentConfig:
    pubkey: PublicKey
    serum_program_id: PublicKey
    serum_market: PublicKey
    serum_request_queue: PublicKey
    serum_event_queue: PublicKey
    serum_bids: PublicKey
    serum_asks: PublicKey
    serum_base_vault: PublicKey
    serum_quote_vault: PublicKey
    serum_open_orders: PublicKey
    serum_signer_nonce: int
    market_index: int
    fulfillment_type: SpotFulfillmentType
    status: SpotFulfillmentConfigStatus
    padding: list[int]
 
@dataclass
class State:
    admin: PublicKey
    whitelist_mint: PublicKey
    discount_mint: PublicKey
    signer: PublicKey
    srm_vault: PublicKey
    perp_fee_structure: FeeStructure
    spot_fee_structure: FeeStructure
    oracle_guard_rails: OracleGuardRails
    number_of_authorities: int
    number_of_sub_accounts: int
    lp_cooldown_time: int
    liquidation_margin_buffer_ratio: int
    settlement_duration: int
    number_of_markets: int
    number_of_spot_markets: int
    signer_nonce: int
    min_perp_auction_duration: int
    default_market_order_time_in_force: int
    default_spot_auction_duration: int
    exchange_status: ExchangeStatus
    liquidation_duration: int
    initial_pct_to_liquidate: int
    padding: list[int]
 
@dataclass
class PerpPosition:
    last_cumulative_funding_rate: int
    base_asset_amount: int
    quote_asset_amount: int
    quote_break_even_amount: int
    quote_entry_amount: int
    open_bids: int
    open_asks: int
    settled_pnl: int
    lp_shares: int
    last_base_asset_amount_per_lp: int
    last_quote_asset_amount_per_lp: int
    remainder_base_asset_amount: int
    market_index: int
    open_orders: int
    padding: list[int]
 
@dataclass
class User:
    authority: PublicKey
    delegate: PublicKey
    name: list[int]
    spot_positions: list[SpotPosition]
    perp_positions: list[PerpPosition]
    orders: list[Order]
    last_add_perp_lp_shares_ts: int
    total_deposits: int
    total_withdraws: int
    total_social_loss: int
    settled_perp_pnl: int
    cumulative_spot_fees: int
    cumulative_perp_funding: int
    liquidation_margin_freed: int
    liquidation_start_slot: int
    next_order_id: int
    max_margin_ratio: int
    next_liquidation_id: int
    sub_account_id: int
    status: UserStatus
    is_margin_trading_enabled: bool
    padding: list[int]
 
@dataclass
class UserFees:
    total_fee_paid: int
    total_fee_rebate: int
    total_token_discount: int
    total_referee_discount: int
    total_referrer_reward: int
    current_epoch_referrer_reward: int
 
@dataclass
class UserStats:
    authority: PublicKey
    referrer: PublicKey
    fees: UserFees
    next_epoch_ts: int
    maker_volume30d: int
    taker_volume30d: int
    filler_volume30d: int
    last_maker_volume30d_ts: int
    last_taker_volume30d_ts: int
    last_filler_volume30d_ts: int
    if_staked_quote_asset_amount: int
    number_of_sub_accounts: int
    number_of_sub_accounts_created: int
    is_referrer: bool
    padding: list[int]
 
@dataclass
class LiquidatePerpRecord:
    market_index: int
    oracle_price: int
    base_asset_amount: int
    quote_asset_amount: int
    lp_shares: int
    fill_record_id: int
    user_order_id: int
    liquidator_order_id: int
    liquidator_fee: int
    if_fee: int
 
@dataclass
class LiquidateSpotRecord:
    asset_market_index: int
    asset_price: int
    asset_transfer: int
    liability_market_index: int
    liability_price: int
    liability_transfer: int
    if_fee: int
 
@dataclass
class LiquidateBorrowForPerpPnlRecord:
    perp_market_index: int
    market_oracle_price: int
    pnl_transfer: int
    liability_market_index: int
    liability_price: int
    liability_transfer: int
 
@dataclass
class LiquidatePerpPnlForDepositRecord:
    perp_market_index: int
    market_oracle_price: int
    pnl_transfer: int
    asset_market_index: int
    asset_price: int
    asset_transfer: int
 
@dataclass
class PerpBankruptcyRecord:
    market_index: int
    pnl: int
    if_payment: int
    clawback_user: Optional[PublicKey]
    clawback_user_payment: Optional[int]
    cumulative_funding_rate_delta: int
 
@dataclass
class SpotBankruptcyRecord:
    market_index: int
    borrow_amount: int
    if_payment: int
    cumulative_deposit_interest_delta: int
 
@dataclass
class InsuranceFundStake:
    authority: PublicKey
    if_shares: int
    last_withdraw_request_shares: int
    if_base: int
    last_valid_ts: int
    last_withdraw_request_value: int
    last_withdraw_request_ts: int
    cost_basis: int
    market_index: int
    padding: list[int]
 
