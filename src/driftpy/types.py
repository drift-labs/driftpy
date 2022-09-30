from dataclasses import dataclass
from solana.publickey import PublicKey
from borsh_construct.enum import _rust_enum
from sumtypes import constructor
from typing import Optional

@_rust_enum
class SpotFulfillmentType:
    SERUM_V3 = constructor()
    NONE = constructor()
 
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
class OracleValidity:
    INVALID = constructor()
    TOO_VOLATILE = constructor()
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
    INSUFFICIENT_FREE_COLLATERAL = constructor()
    ORACLE_PRICE_BREACHED_LIMIT_PRICE = constructor()
    MARKET_ORDER_FILLED_TO_LIMIT_PRICE = constructor()
    ORDER_EXPIRED = constructor()
    CANCELED_FOR_LIQUIDATION = constructor()
    ORDER_FILLED_WITH_A_M_M = constructor()
    ORDER_FILLED_WITH_MATCH = constructor()
 
@_rust_enum
class LPAction:
    ADD_LIQUIDITY = constructor()
    REMOVE_LIQUIDITY = constructor()
    SETTLE_LIQUIDITY = constructor()
 
@_rust_enum
class LiquidationType:
    LIQUIDATE_PERP = constructor()
    LIQUIDATE_BORROW = constructor()
    LIQUIDATE_BORROW_FOR_PERP_PNL = constructor()
    LIQUIDATE_PERP_PNL_FOR_DEPOSIT = constructor()
    PERP_BANKRUPTCY = constructor()
    BORROW_BANKRUPTCY = constructor()
 
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
class MarketStatus:
    INITIALIZED = constructor()
    REDUCE_ONLY = constructor()
    SETTLEMENT = constructor()
    DELISTED = constructor()
 
@_rust_enum
class ContractType:
    PERPETUAL = constructor()
    FUTURE = constructor()
 
@_rust_enum
class OracleSource:
    PYTH = constructor()
    SWITCHBOARD = constructor()
    QUOTE_ASSET = constructor()
 
@_rust_enum
class SpotBalanceType:
    DEPOSIT = constructor()
    BORROW = constructor()
 
@_rust_enum
class SpotFulfillmentStatus:
    ENABLED = constructor()
    DISABLED = constructor()
 
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
 
@_rust_enum
class OrderTriggerCondition:
    ABOVE = constructor()
    BELOW = constructor()
 
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
    trigger_price: int
    trigger_condition: OrderTriggerCondition
    oracle_price_offset: int
    auction_duration: Optional[int]
    time_in_force: Optional[int]
    auction_start_price: Optional[int]
 
@dataclass
class HistoricalOracleData:
    last_oracle_price: int
    last_oracle_conf: int
    last_oracle_delay: int
    last_oracle_price_twap: int
    last_oracle_price_twap5min: int
    last_oracle_price_twap_ts: int
 
@dataclass
class PerpPosition:
    market_index: int
    base_asset_amount: int
    quote_asset_amount: int
    quote_entry_amount: int
    last_cumulative_funding_rate: int
    last_funding_rate_ts: int
    open_orders: int
    open_bids: int
    open_asks: int
    settled_pnl: int
    lp_shares: int
    remainder_base_asset_amount: int
    last_net_base_asset_amount_per_lp: int
    last_net_quote_asset_amount_per_lp: int
    last_lp_add_time: int
 
@dataclass
class PoolBalance:
    balance: int
 
@dataclass
class AMM:
    oracle: PublicKey
    oracle_source: OracleSource
    historical_oracle_data: HistoricalOracleData
    last_oracle_valid: bool
    last_update_slot: int
    last_oracle_conf_pct: int
    last_oracle_normalised_price: int
    last_oracle_reserve_price_spread_pct: int
    base_asset_reserve: int
    quote_asset_reserve: int
    concentration_coef: int
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
    market_position_per_lp: PerpPosition
    amm_jit_intensity: int
    last_funding_rate: int
    last_funding_rate_long: int
    last_funding_rate_short: int
    last24h_avg_funding_rate: int
    last_funding_rate_ts: int
    funding_period: int
    cumulative_funding_rate_long: int
    cumulative_funding_rate_short: int
    cumulative_social_loss: int
    minimum_quote_asset_trade_size: int
    max_base_asset_amount_ratio: int
    max_slippage_ratio: int
    base_asset_amount_step_size: int
    market_position: PerpPosition
    base_spread: int
    long_spread: int
    short_spread: int
    max_spread: int
    ask_base_asset_reserve: int
    ask_quote_asset_reserve: int
    bid_base_asset_reserve: int
    bid_quote_asset_reserve: int
    volume24h: int
    long_intensity_count: int
    long_intensity_volume: int
    short_intensity_count: int
    short_intensity_volume: int
    curve_update_intensity: int
    last_trade_ts: int
    mark_std: int
    last_bid_price_twap: int
    last_ask_price_twap: int
    last_mark_price_twap: int
    last_mark_price_twap5min: int
    last_mark_price_twap_ts: int
    total_fee: int
    total_mm_fee: int
    total_exchange_fee: int
    total_fee_minus_distributions: int
    total_fee_withdrawn: int
    net_revenue_since_last_funding: int
    total_liquidation_fee: int
    fee_pool: PoolBalance
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
    slots_before_stale_for_amm: int
    slots_before_stale_for_margin: int
    confidence_interval_max_size: int
    too_volatile_ratio: int
 
@dataclass
class OracleGuardRails:
    price_divergence: PriceDivergenceGuardRails
    validity: ValidityGuardRails
    use_for_liquidations: bool
 
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
    market_index: int
    balance_type: SpotBalanceType
    balance: int
    open_orders: int
    open_bids: int
    open_asks: int
    cumulative_deposits: int
 
@dataclass
class Order:
    status: OrderStatus
    order_type: OrderType
    market_type: MarketType
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
    trigger_price: int
    trigger_condition: OrderTriggerCondition
    triggered: bool
    oracle_price_offset: int
    auction_start_price: int
    auction_end_price: int
    auction_duration: int
    time_in_force: int
 
@dataclass
class PerpMarket:
    market_index: int
    pubkey: PublicKey
    status: MarketStatus
    contract_type: ContractType
    settlement_price: int
    expiry_ts: int
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
    revenue_withdraw_since_last_settle: int
    max_revenue_withdraw_per_period: int
    last_revenue_withdraw_ts: int
    imf_factor: int
    unrealized_initial_asset_weight: int
    unrealized_maintenance_asset_weight: int
    unrealized_imf_factor: int
    unrealized_max_imbalance: int
    liquidator_fee: int
    if_liquidation_fee: int
    quote_max_insurance: int
    quote_settled_insurance: int
    padding0: int
    padding1: int
    padding2: int
    padding3: int
    padding4: int
 
@dataclass
class HistoricalIndexData:
    last_index_bid_price: int
    last_index_ask_price: int
    last_index_price_twap: int
    last_index_price_twap5min: int
    last_index_price_twap_ts: int
 
@dataclass
class SpotMarket:
    market_index: int
    pubkey: PublicKey
    status: MarketStatus
    expiry_ts: int
    oracle: PublicKey
    oracle_source: OracleSource
    historical_oracle_data: HistoricalOracleData
    historical_index_data: HistoricalIndexData
    mint: PublicKey
    vault: PublicKey
    insurance_fund_vault: PublicKey
    revenue_pool: PoolBalance
    total_if_factor: int
    user_if_factor: int
    total_if_shares: int
    user_if_shares: int
    if_shares_base: int
    insurance_withdraw_escrow_period: int
    last_revenue_settle_ts: int
    revenue_settle_period: int
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
    liquidator_fee: int
    if_liquidation_fee: int
    withdraw_guard_threshold: int
    order_step_size: int
    next_fill_record_id: int
    total_spot_fee: int
    spot_fee_pool: PoolBalance
 
@dataclass
class SerumV3FulfillmentConfig:
    pubkey: PublicKey
    fulfillment_type: SpotFulfillmentType
    status: SpotFulfillmentStatus
    market_index: int
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
 
@dataclass
class State:
    admin: PublicKey
    exchange_paused: bool
    funding_paused: bool
    admin_controls_prices: bool
    whitelist_mint: PublicKey
    discount_mint: PublicKey
    oracle_guard_rails: OracleGuardRails
    number_of_markets: int
    number_of_spot_markets: int
    min_order_quote_asset_amount: int
    min_perp_auction_duration: int
    default_market_order_time_in_force: int
    default_spot_auction_duration: int
    liquidation_margin_buffer_ratio: int
    settlement_duration: int
    signer: PublicKey
    signer_nonce: int
    srm_vault: PublicKey
    perp_fee_structure: FeeStructure
    spot_fee_structure: FeeStructure
 
@dataclass
class User:
    authority: PublicKey
    delegate: PublicKey
    user_id: int
    name: list[int]
    spot_positions: list[SpotPosition]
    next_order_id: int
    perp_positions: list[PerpPosition]
    orders: list[Order]
    next_liquidation_id: int
    being_liquidated: bool
    bankrupt: bool
    custom_margin_ratio: int
 
@dataclass
class UserFees:
    total_fee_paid: int
    total_lp_fees: int
    total_fee_rebate: int
    total_token_discount: int
    total_referee_discount: int
 
@dataclass
class UserStats:
    authority: PublicKey
    number_of_users: int
    is_referrer: bool
    referrer: PublicKey
    total_referrer_reward: int
    current_epoch_referrer_reward: int
    next_epoch_ts: int
    fees: UserFees
    maker_volume30d: int
    taker_volume30d: int
    filler_volume30d: int
    last_maker_volume30d_ts: int
    last_taker_volume30d_ts: int
    last_filler_volume30d_ts: int
    staked_quote_asset_amount: int
 
