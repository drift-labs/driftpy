import inspect
import zlib
from dataclasses import dataclass, field
from typing import Optional, TypedDict
from urllib.parse import urlparse, urlunparse

from borsh_construct.enum import _rust_enum
from solana.rpc.commitment import Commitment
from solders.pubkey import Pubkey
from sumtypes import constructor
from typing_extensions import NotRequired


def is_variant(enum, type: str) -> bool:
    return type == enum.__class__.__name__


def is_one_of_variant(enum, types):
    return any(type in str(enum) for type in types)


def get_ws_url(url: str) -> str:
    parsed = urlparse(url)

    if parsed.port:
        ws_port = parsed.port + 1
        new_netloc = f"{parsed.hostname}:{ws_port}"
        new_scheme = "wss" if parsed.scheme == "https" else "ws"
        return urlunparse(
            (
                new_scheme,
                new_netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment,
            )
        )
    else:
        return url.replace("https", "wss").replace("http", "ws")


def stack_trace():
    caller_frame = inspect.stack()[1]
    frame_info = inspect.getframeinfo(caller_frame[0])

    file_name = frame_info.filename
    line_number = frame_info.lineno

    return f"{file_name}:{line_number}"


def compress(data: bytes) -> bytes:
    return zlib.compress(data, level=9)


def decompress(data: bytes) -> bytes:
    return zlib.decompress(data)


@_rust_enum
class SwapDirection:
    Add = constructor()
    Remove = constructor()


@_rust_enum
class PositionDirection:
    Long = constructor()
    Short = constructor()


@_rust_enum
class SpotFulfillmentType:
    SERUM_V3 = constructor()
    MATCH = constructor()
    PHOENIX_V1 = constructor()


@_rust_enum
class SwapReduceOnly:
    In = constructor()
    Out = constructor()


@_rust_enum
class TwapPeriod:
    FundingPeriod = constructor()
    FiveMin = constructor()


@_rust_enum
class LiquidationMultiplierType:
    Discount = constructor()
    Premium = constructor()


@_rust_enum
class MarginRequirementType:
    INITIAL = constructor()
    FILL = constructor()
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
    Transfer = constructor()


@_rust_enum
class DepositDirection:
    Deposit = constructor()
    Withdraw = constructor()


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
    InsufficientFreeCollateral = constructor()
    OraclePriceBreachedLimitPrice = constructor()
    MarketOrderFilledToLimitPrice = constructor()
    OrderExpired = constructor()
    Liquidation = constructor()
    OrderFilledWithAmm = constructor()
    OrderFilledWithAmmJit = constructor()
    OrderFilledWithMatch = constructor()
    OrderFilledWithMatchJit = constructor()
    MarketExpired = constructor()
    RiskIncreasingOrder = constructor()
    ReduceOnlyOrderIncreasePosition = constructor()
    OrderFillWithSerum = constructor()
    NoBorrowLiquidity = constructor()
    OrderFillWithPhoenix = constructor()
    OrderFilledWithAmmJitLpSplit = constructor()
    OrderFilledWithLpJit = constructor()


@_rust_enum
class LPAction:
    AddLiquidity = constructor()
    RemoveLiquidity = constructor()
    SettleLiquidity = constructor()


@_rust_enum
class LiquidationType:
    LiquidatePerp = constructor()
    LiquidateSpot = constructor()
    LiquidateBorrowForPerpPnl = constructor()
    LiquidatePerpPnlForDeposit = constructor()
    PerpBankruptcy = constructor()
    SpotBankruptcy = constructor()


@_rust_enum
class SettlePnlExplanation:
    NONE = constructor()
    Expired = constructor()


@_rust_enum
class StakeAction:
    Stake = constructor()
    UnstakeRequest = constructor()
    UnstakeCancelRequest = constructor()
    Unstake = constructor()
    UnstakeTransfer = constructor()
    StakeTransfer = constructor()


@_rust_enum
class FillMode:
    FILL = constructor()
    PLACE_AND_MAKE = constructor()
    PLACE_AND_TAKE = constructor()


@_rust_enum
class PerpFulfillmentMethod:
    A_M_M = constructor()
    MATCH = constructor()


@_rust_enum
class SpotFulfillmentMethod:
    EXTERNAL_MARKET = constructor()
    MATCH = constructor()


@_rust_enum
class MarginCalculationMode:
    STANDARD = constructor()
    LIQUIDATION = constructor()


@_rust_enum
class OracleSource:
    Pyth = constructor()
    Switchboard = constructor()
    QuoteAsset = constructor()
    Pyth1K = constructor()
    Pyth1M = constructor()
    PythStableCoin = constructor()
    Prelaunch = constructor()
    PythPull = constructor()
    Pyth1KPull = constructor()
    Pyth1MPull = constructor()
    PythStableCoinPull = constructor()
    SwitchboardOnDemand = constructor()
    PythLazer = constructor()
    PythLazer1K = constructor()
    PythLazer1M = constructor()
    PythLazerStableCoin = constructor()


@_rust_enum
class PostOnlyParams:
    NONE = constructor()
    MustPostOnly = constructor()
    TryPostOnly = constructor()
    Slide = constructor()


@_rust_enum
class ModifyOrderPolicy:
    TRY_MODIFY = constructor()
    MUST_MODIFY = constructor()


@_rust_enum
class MarketStatus:
    Initialized = constructor()
    Active = constructor()
    FundingPaused = constructor()
    AmmPaused = constructor()
    FillPaused = constructor()
    WithdrawPaused = constructor()
    ReduceOnly = constructor()
    Settlement = constructor()
    Delisted = constructor()


@_rust_enum
class ContractType:
    Perpetual = constructor()
    Future = constructor()
    Prediction = constructor()


@_rust_enum
class ContractTier:
    A = constructor()
    B = constructor()
    C = constructor()
    Speculative = constructor()
    HighlySpeculative = constructor()
    Isolated = constructor()


@_rust_enum
class AMMLiquiditySplit:
    PROTOCOL_OWNED = constructor()
    L_P_OWNED = constructor()
    SHARED = constructor()


@_rust_enum
class SpotBalanceType:
    Deposit = constructor()
    Borrow = constructor()


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
    Active = constructor()
    DepositPaused = constructor()
    WithdrawPaused = constructor()
    AmmPaused = constructor()
    FillPaused = constructor()
    LiqPaused = constructor()
    FundingPaused = constructor()
    SettlePnlPaused = constructor()


class UserStatus:
    BEING_LIQUIDATED = 1
    BANKRUPT = 2
    REDUCE_ONLY = 4
    ADVANCED_UP = 8
    PROTECTED_MAKER = 16


@_rust_enum
class MarginMode:
    Default = constructor()
    HighLeverage = constructor()


@_rust_enum
class OrderStatus:
    Init = constructor()
    Open = constructor()
    Filled = constructor()
    Canceled = constructor()


class OracleSourceNum:
    PYTH = 0
    SWITCHBOARD = 6
    QUOTE_ASSET = 7
    PYTH_1K = 1
    PYTH_1M = 2
    PYTH_STABLE_COIN = 8
    PRELAUNCH = 10
    PYTH_PULL = 3
    PYTH_1K_PULL = 4
    PYTH_1M_PULL = 5
    PYTH_STABLE_COIN_PULL = 9
    SWITCHBOARD_ON_DEMAND = 11
    PYTH_LAZER = 12
    PYTH_LAZER_1K = 13
    PYTH_LAZER_1M = 14
    PYTH_LAZER_STABLE_COIN = 15


@_rust_enum
class OrderType:
    Market = constructor()
    Limit = constructor()
    TriggerMarket = constructor()
    TriggerLimit = constructor()
    Oracle = constructor()


@_rust_enum
class OrderTriggerCondition:
    Above = constructor()
    Below = constructor()
    TriggeredAbove = constructor()
    TriggeredBelow = constructor()


@_rust_enum
class MarketType:
    Spot = constructor()
    Perp = constructor()


def market_type_to_string(market_type: MarketType):
    type_str = str(type(market_type))
    if "Perp" in type_str:
        return "perp"
    elif "Spot" in type_str:
        return "spot"
    else:
        raise ValueError("Unknown market type, not Spot or Perp")


@dataclass
class MarketIdentifier:
    market_type: MarketType
    market_index: int


@dataclass
class OrderParams:
    order_type: OrderType
    base_asset_amount: int
    market_index: int
    direction: PositionDirection
    market_type: MarketType
    user_order_id: int = 0
    price: int = 0
    reduce_only: bool = False
    post_only: PostOnlyParams = field(default_factory=PostOnlyParams.NONE)
    immediate_or_cancel: bool = False
    max_ts: Optional[int] = None
    trigger_price: Optional[int] = None
    trigger_condition: OrderTriggerCondition = field(
        default_factory=OrderTriggerCondition.Above
    )
    oracle_price_offset: Optional[int] = None
    auction_duration: Optional[int] = None
    auction_start_price: Optional[int] = None
    auction_end_price: Optional[int] = None

    def set_spot(self):
        self.market_type = MarketType.Spot()

    def set_perp(self):
        self.market_type = MarketType.Perp()

    def check_market_type(self):
        if self.market_type is None:
            raise ValueError("market type not set on order params")


@dataclass
class ModifyOrderParams:
    direction: Optional[PositionDirection] = None
    base_asset_amount: Optional[int] = None
    price: Optional[int] = None
    reduce_only: Optional[bool] = None
    post_only: Optional[PostOnlyParams] = None
    immediate_or_cancel: Optional[bool] = None
    max_ts: Optional[int] = None
    trigger_price: Optional[int] = None
    trigger_condition: Optional[OrderTriggerCondition] = None
    oracle_price_offset: Optional[int] = None
    auction_duration: Optional[int] = None
    auction_start_price: Optional[int] = None
    auction_end_price: Optional[int] = None
    policy: Optional[ModifyOrderPolicy] = None


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
    padding: list[int] = field(default_factory=lambda: [0] * 6)


@dataclass
class AMM:
    oracle: Pubkey
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
    target_base_asset_amount_per_lp: int
    per_lp_base: int
    padding1: int = 0
    padding2: int = 0
    total_fee_earned_per_lp: Optional[int] = None
    padding: list[int] = field(default_factory=lambda: [0] * 12)


@dataclass
class PriceDivergenceGuardRails:
    mark_oracle_percent_divergence: int
    oracle_twap5min_percent_divergence: int


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
    padding: list[int] = field(default_factory=lambda: [0] * 4)


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
    posted_slot_tail: int
    bit_flags: int
    padding: list[int] = field(default_factory=lambda: [0] * 1)


@dataclass
class PhoenixV1FulfillmentConfigAccount:
    pubkey: Pubkey
    phoenix_program_id: Pubkey
    phoenix_log_authority: Pubkey
    phoenix_market: Pubkey
    phoenix_base_vault: Pubkey
    phoenix_quote_vault: Pubkey
    market_index: int
    fulfillment_type: SpotFulfillmentType
    status: SpotFulfillmentConfigStatus
    padding: list[int] = field(default_factory=lambda: [0] * 4)


@dataclass
class SerumV3FulfillmentConfigAccount:
    pubkey: Pubkey
    serum_program_id: Pubkey
    serum_market: Pubkey
    serum_request_queue: Pubkey
    serum_event_queue: Pubkey
    serum_bids: Pubkey
    serum_asks: Pubkey
    serum_base_vault: Pubkey
    serum_quote_vault: Pubkey
    serum_open_orders: Pubkey
    serum_signer_nonce: int
    market_index: int
    fulfillment_type: SpotFulfillmentType
    status: SpotFulfillmentConfigStatus
    padding: list[int] = field(default_factory=lambda: [0] * 4)


@dataclass
class InsuranceClaim:
    revenue_withdraw_since_last_settle: int
    max_revenue_withdraw_per_period: int
    quote_max_insurance: int
    quote_settled_insurance: int
    last_revenue_withdraw_ts: int


@dataclass
class PerpMarketAccount:
    pubkey: Pubkey
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
    paused_operations: int
    quote_spot_market_index: int
    fee_adjustment: int

    fuel_boost_taker: int
    fuel_boost_maker: int
    fuel_boost_position: int

    pool_id: int
    high_leverage_margin_ratio_initial: int
    high_leverage_margin_ratio_maintenance: int

    padding: list[int] = field(default_factory=lambda: [0] * 38)


@dataclass
class HistoricalIndexData:
    last_index_bid_price: int
    last_index_ask_price: int
    last_index_price_twap: int
    last_index_price_twap5min: int
    last_index_price_twap_ts: int


@dataclass
class InsuranceFund:
    vault: Pubkey
    total_shares: int
    user_shares: int
    shares_base: int
    unstaking_period: int
    last_revenue_settle_ts: int
    revenue_settle_period: int
    total_factor: int
    user_factor: int


@dataclass
class SpotMarketAccount:
    pubkey: Pubkey
    oracle: Pubkey
    mint: Pubkey
    vault: Pubkey
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
    paused_operations: int
    if_paused_operations: int
    fee_adjustment: int
    max_token_borrows_fraction: int
    flash_loan_amount: Optional[int] = None
    flash_loan_initial_token_amount: Optional[int] = None
    total_swap_fee: Optional[int] = None
    scale_initial_asset_weight_start: Optional[int] = None
    min_borrow_rate: Optional[int] = None
    fuel_boost_deposits: Optional[int] = None
    fuel_boost_borrows: Optional[int] = None
    fuel_boost_taker: Optional[int] = None
    fuel_boost_maker: Optional[int] = None
    fuel_boost_insurance: Optional[int] = None
    padding: list[int] = field(default_factory=lambda: [0] * 42)


@dataclass
class StateAccount:
    admin: Pubkey
    whitelist_mint: Pubkey
    discount_mint: Pubkey
    signer: Pubkey
    srm_vault: Pubkey
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
    exchange_status: int
    liquidation_duration: int
    initial_pct_to_liquidate: int
    max_number_of_sub_accounts: int
    padding: list[int] = field(default_factory=lambda: [0] * 10)


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
    per_lp_base: int


@dataclass
class UserAccount:
    authority: Pubkey
    delegate: Pubkey
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
    last_active_slot: int
    next_order_id: int
    max_margin_ratio: int
    next_liquidation_id: int
    sub_account_id: int
    status: int
    is_margin_trading_enabled: bool
    idle: bool
    open_orders: int
    has_open_order: bool
    open_auctions: int
    has_open_auction: bool
    margin_mode: MarginMode
    padding: list[int] = field(default_factory=lambda: [0] * 21)


@dataclass
class PickledData:
    pubkey: Pubkey
    data: bytes


@dataclass
class UserFees:
    total_fee_paid: int
    total_fee_rebate: int
    total_token_discount: int
    total_referee_discount: int
    total_referrer_reward: int
    current_epoch_referrer_reward: int


@dataclass
class UserStatsAccount:
    authority: Pubkey
    referrer: Pubkey
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
    disable_update_perp_bid_ask_twap: bool
    padding1: list[int] = (field(default_factory=lambda: [0] * 2),)
    last_fuel_bonus_update_ts: int = (0,)
    fuel_insurance: int = (0,)
    fuel_deposits: int = (0,)
    fuel_borrows: int = (0,)
    fuel_positions: int = (0,)
    fuel_taker: int = (0,)
    fuel_maker: int = (0,)
    if_staked_gov_token_amount: int = (0,)
    padding: list[int] = field(default_factory=lambda: [0] * 12)


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
    clawback_user: Optional[Pubkey]
    clawback_user_payment: Optional[int]
    cumulative_funding_rate_delta: int


@dataclass
class SpotBankruptcyRecord:
    market_index: int
    borrow_amount: int
    if_payment: int
    cumulative_deposit_interest_delta: int


@dataclass
class InsuranceFundStakeAccount:
    authority: Pubkey
    if_shares: int
    last_withdraw_request_shares: int
    if_base: int
    last_valid_ts: int
    last_withdraw_request_value: int
    last_withdraw_request_ts: int
    cost_basis: int
    market_index: int
    padding: list[int] = field(default_factory=lambda: [0] * 14)


@dataclass
class ProtocolIfSharesTransferConfigAccount:
    whitelisted_signers: list[Pubkey]
    max_transfer_per_epoch: int
    current_epoch_transfer: int
    next_epoch_ts: int
    padding: list[int] = field(default_factory=lambda: [0] * 8)


@dataclass
class ReferrerNameAccount:
    authority: Pubkey
    user: Pubkey
    user_stats: Pubkey
    name: list[int]


@dataclass
class OraclePriceData:
    price: int
    slot: int
    confidence: int
    twap: int
    twap_confidence: int
    has_sufficient_number_of_data_points: bool

    @staticmethod
    def default():
        return OraclePriceData(
            price=0,
            slot=0,
            confidence=0,
            twap=0,
            twap_confidence=0,
            has_sufficient_number_of_data_points=False,
        )


@dataclass
class TxParams:
    compute_units: Optional[int]
    compute_units_price: Optional[int]


@_rust_enum
class AssetType:
    QUOTE = constructor()
    BASE = constructor()


@dataclass
class MakerInfo:
    maker: Pubkey
    maker_stats: Pubkey
    maker_user_account: UserAccount
    order: Optional[Order] = None


@dataclass
class ReferrerInfo:
    referrer: Pubkey
    referrer_stats: Pubkey


@dataclass
class OracleInfo:
    pubkey: Pubkey
    source: OracleSource


@dataclass
class NewUserRecord:
    ts: int
    user_authority: Pubkey
    user: Pubkey
    sub_account_id: int
    name: list[int]
    referrer: Pubkey


@dataclass
class DepositRecord:
    ts: int
    user_authority: Pubkey
    user: Pubkey
    direction: DepositDirection
    market_index: int
    amount: int
    oracle_price: int
    market_deposit_balance: int
    market_withdraw_balance: int
    market_cumulative_deposit_interest: int
    market_cumulative_borrow_interest: int
    total_deposits_after: int
    total_withdraws_after: int
    deposit_record_id: int
    explanation: DepositExplanation
    transfer_user: Optional[Pubkey]


@dataclass
class SpotInterestRecord:
    ts: int
    market_index: int
    deposit_balance: int
    cumulative_deposit_interest: int
    borrow_balance: int
    cumulative_borrow_interest: int
    optimal_utilization: int
    optimal_borrow_rate: int
    max_borrow_rate: int


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
    base_asset_amount_with_amm: int
    total_fee: int
    total_fee_minus_distributions: int
    adjustment_cost: int
    number_of_users: int
    oracle_price: int
    fill_record: int


@dataclass
class InsuranceFundRecord:
    ts: int
    spot_market_index: int
    perp_market_index: int
    user_if_factor: int
    total_if_factor: int
    vault_amount_before: int
    insurance_vault_amount_before: int
    total_if_shares_before: int
    total_if_shares_after: int
    amount: int


@dataclass
class InsuranceFundStakeRecord:
    ts: int
    user_authority: Pubkey
    action: StakeAction
    amount: int
    market_index: int
    insurance_vault_amount_before: int
    if_shares_before: int
    user_if_shares_before: int
    total_if_shares_before: int
    if_shares_after: int
    user_if_shares_after: int
    total_if_shares_after: int


@dataclass
class LPRecord:
    ts: int
    user: Pubkey
    action: LPAction
    n_shares: int
    market_index: int
    delta_base_asset_amount: int
    delta_quote_asset_amount: int
    pnl: int


@dataclass
class FundingRateRecord:
    ts: int
    record_id: int
    market_index: int
    funding_rate: int
    funding_rate_long: int
    funding_rate_short: int
    cumulative_funding_rate_long: int
    cumulative_funding_rate_short: int
    oracle_price_twap: int
    mark_price_twap: int
    period_revenue: int
    base_asset_amount_with_amm: int
    base_asset_amount_with_unsettled_lp: int


@dataclass
class FundingPaymentRecord:
    ts: int
    user_authority: Pubkey
    user: Pubkey
    market_index: int
    funding_payment: int
    base_asset_amount: int
    user_last_cumulative_funding: int
    amm_cumulative_funding_long: int
    amm_cumulative_funding_short: int


@dataclass
class LiquidatePerpRecord:
    market_index: int
    oracle_price: int
    base_asset_amount: int
    quote_asset_amount: int
    lp_shares: int
    user_order_id: int
    liquidator_order_id: int
    fill_record_id: int
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
    clawback_user: Pubkey
    clawback_user_payment: int
    cumulative_funding_rate_delta: int


@dataclass
class SpotBankruptcyRecord:
    market_index: int
    borrow_amount: int
    cumulative_deposit_interest_delta: int
    if_payment: int


@dataclass
class LiquidationRecord:
    ts: int
    user: Pubkey
    liquidator: Pubkey
    liquidation_type: LiquidationType
    margin_requirement: int
    total_collateral: int
    margin_freed: int
    liquidation_id: int
    bankrupt: bool
    canceled_order_ids: list[int]
    liquidate_perp: LiquidatePerpRecord
    liquidate_spot: LiquidateSpotRecord
    liquidate_borrow_for_perp_pnl: LiquidateBorrowForPerpPnlRecord
    liquidate_perp_pnl_for_deposit: LiquidatePerpPnlForDepositRecord
    perp_bankruptcy: PerpBankruptcyRecord
    spot_bankruptcy: SpotBankruptcyRecord


@dataclass
class SettlePnlRecord:
    ts: int
    user: Pubkey
    market_index: int
    pnl: int
    base_asset_amount: int
    quote_asset_amount_after: int
    quote_entry_amount: int
    settle_price: int
    explanation: SettlePnlExplanation


@dataclass
class OrderRecord:
    ts: int
    user: Pubkey
    order: Order


@dataclass
class OrderActionRecord:
    ts: int
    action: OrderAction
    action_explanation: OrderActionExplanation
    market_index: int
    market_type: MarketType
    filler: Optional[Pubkey]
    filler_reward: Optional[int]
    fill_record_id: Optional[int]
    base_asset_amount_filled: Optional[int]
    quote_asset_amount_filled: Optional[int]
    taker_fee: Optional[int]
    maker_fee: Optional[int]
    referrer_reward: Optional[int]
    quote_asset_amount_surplus: Optional[int]
    spot_fulfillment_method_fee: Optional[int]
    taker: Optional[Pubkey]
    taker_order_id: Optional[int]
    taker_order_direction: Optional[PositionDirection]
    taker_order_base_asset_amount: Optional[int]
    taker_order_cumulative_base_asset_amount_filled: Optional[int]
    taker_order_cumulative_quote_asset_amount_filled: Optional[int]
    maker: Optional[Pubkey]
    maker_order_id: Optional[int]
    maker_order_direction: Optional[PositionDirection]
    maker_order_base_asset_amount: Optional[int]
    maker_order_cumulative_base_asset_amount_filled: Optional[int]
    maker_order_cumulative_quote_asset_amount_filled: Optional[int]
    oracle_price: int


@dataclass
class SwapRecord:
    ts: int
    user: Pubkey
    amount_out: int
    amount_in: int
    out_market_index: int
    in_market_index: int
    out_oracle_price: int
    in_oracle_price: int
    fee: int


@dataclass
class PrelaunchOracleParams:
    perp_market_index: int
    price: Optional[int]
    max_price: Optional[int]


@dataclass
class PrelaunchOracle:
    price: int
    max_price: int
    confidence: int
    amm_last_update_slot: int
    last_update_slot: int
    perp_market_index: int


@dataclass
class SequenceAccount:
    sequence_num: int
    authority: Pubkey


@dataclass
class PriceFeedMessage:
    price: int
    conf: int
    exponent: int
    ema_price: int
    ema_conf: int


@dataclass
class PriceUpdateV2:
    price_message: PriceFeedMessage
    posted_slot: int


@dataclass
class GrpcConfig:
    endpoint: str
    token: str
    commitment: Commitment = Commitment("confirmed")


class OptionalOrderParams(TypedDict, total=False):
    """All fields are optional except market_type, market_index, direction"""

    order_type: NotRequired[OrderType]
    base_asset_amount: NotRequired[int]
    price: NotRequired[int]
    market_index: int  # required
    direction: PositionDirection  # required
    market_type: MarketType  # required
    user_order_id: NotRequired[int]
    reduce_only: NotRequired[bool]
    post_only: NotRequired[PostOnlyParams]
    immediate_or_cancel: NotRequired[bool]
    max_ts: NotRequired[Optional[int]]
    trigger_price: NotRequired[Optional[int]]
    trigger_condition: NotRequired[OrderTriggerCondition]
    oracle_price_offset: NotRequired[Optional[int]]
    auction_duration: NotRequired[Optional[int]]
    auction_start_price: NotRequired[Optional[int]]
    auction_end_price: NotRequired[Optional[int]]


@dataclass
class SignedMsgOrderParams:
    order_params: bytes
    signature: bytes


@dataclass
class SignedMsgTriggerOrderParams:
    trigger_price: int
    base_asset_amount: int


@dataclass
class SignedMsgOrderParamsMessage:
    signed_order_params: OptionalOrderParams
    sub_account_id: int
    slot: int
    uuid: bytes
    take_profit_order_params: SignedMsgTriggerOrderParams | None
    stop_loss_order_params: SignedMsgTriggerOrderParams | None
