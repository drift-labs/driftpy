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
    Pyth_1K = constructor()
    Pyth_1M = constructor()


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
    ORACLE = constructor()


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
    last_cumulative_base_asset_amount_with_amm_per_lp: int
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
    oracle_source: OracleSource = OracleSource.Pyth()
    last_oracle_price: int = 0
    last_oracle_conf_pct: int = 0
    last_oracle_delay: int = 0
    last_oracle_normalised_price: int = 0
    last_oracle_price_twap: int = 0
    last_oracle_price_twap_ts: int = 0
    last_oracle_mark_spread_pct: int = 0

    base_asset_reserve: int = 0
    quote_asset_reserve: int = 0
    sqrt_k: int = 0
    peg_multiplier: int = 0

    terminal_quote_asset_reserve: int = 0
    base_asset_amount_with_amm: int = 0
    base_asset_amount_with_unsettled_lp: int = 0

    base_asset_amount_long: int = 0
    base_asset_amount_short: int = 0

    quote_asset_amount_long: int = 0
    quote_asset_amount_short: int = 0

    ## lp stuff
    cumulative_funding_payment_per_lp: int = 0
    cumulative_fee_per_lp: int = 0
    cumulative_base_asset_amount_with_amm_per_lp: int = 0
    lp_cooldown_time: int = 0
    user_lp_shares: int = 0

    ## funding
    last_funding_rate: int = 0
    last_funding_rate_ts: int = 0
    funding_period: int = 0
    cumulative_funding_rate_long: int = 0
    cumulative_funding_rate_short: int = 0
    cumulative_repeg_rebate_long: int = 0
    cumulative_repeg_rebate_short: int = 0

    mark_std: int = 0
    last_mark_price_twap: int = 0
    last_mark_price_twap_ts: int = 0

    ## trade constraints
    minimum_quote_asset_trade_size: int = 0
    base_asset_amount_step_size: int = 0

    ## market making
    base_spread: int = 0
    long_spread: int = 0
    short_spread: int = 0
    max_spread: int = 0
    ask_base_asset_reserve: int = 0
    ask_quote_asset_reserve: int = 0
    bid_base_asset_reserve: int = 0
    bid_quote_asset_reserve: int = 0

    last_bid_price_twap: int = 0
    last_ask_price_twap: int = 0

    long_intensity_count: int = 0
    long_intensity_volume: int = 0
    short_intensity_count: int = 0
    short_intensity_volume: int = 0
    curve_update_intensity: int = 0

    ## fee tracking
    total_fee: int = 0
    total_mm_fee: int = 0
    total_exchange_fee: int = 0
    total_fee_minus_distributions: int = 0
    total_fee_withdrawn: int = 0
    net_revenue_since_last_funding: int = 0
    fee_pool: int = 0
    last_update_slot: int = 0

    padding0: int = 0
    padding1: int = 0
    padding2: int = 0
    padding3: int = 0


@dataclass
class Market:
    market_index: int
    amm: AMM
    pubkey: PublicKey = PublicKey(0)
    initialized: bool = True
    base_asset_amount_long: int = 0
    base_asset_amount_short: int = 0
    number_of_users: int = 0
    margin_ratio_initial: int = 1000
    margin_ratio_partial: int = 500
    margin_ratio_maintenance: int = 625
    next_fill_record_id: int = 0
    next_funding_rate_record_id: int = 0
    next_curve_record_id: int = 0
    pnl_pool: PoolBalance = PoolBalance(0)
    unsettled_profit: int = 0
    unsettled_loss: int = 0

    padding0: int = 0
    padding1: int = 0
    padding2: int = 0
    padding3: int = 0
    padding4: int = 0


from driftpy.types import OracleSource
from driftpy.constants.numeric_constants import SPOT_RATE_PRECISION


@dataclass
class SpotMarket:
    mint: PublicKey  # this
    oracle: PublicKey = PublicKey([0] * PublicKey.LENGTH)  # this
    oracle_source: OracleSource = OracleSource.QUOTE_ASSET()
    optimal_utilization: int = SPOT_RATE_PRECISION // 2
    optimal_rate: int = SPOT_RATE_PRECISION
    max_rate: int = SPOT_RATE_PRECISION
