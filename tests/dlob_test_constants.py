from driftpy.constants.numeric_constants import (
    AMM_TO_QUOTE_PRECISION_RATIO,
    BASE_PRECISION,
    PRICE_PRECISION,
    QUOTE_PRECISION,
    SPOT_CUMULATIVE_INTEREST_PRECISION,
    SPOT_MARKET_CUMULATIVE_INTEREST_PRECISION,
    SPOT_MARKET_CUMULATIVE_INTEREST_PRECISION_EXP,
    SPOT_MARKET_WEIGHT_PRECISION,
)
from driftpy.types import (
    AMM,
    AssetTier,
    ContractTier,
    ContractType,
    HistoricalIndexData,
    HistoricalOracleData,
    InsuranceClaim,
    InsuranceFund,
    MarketStatus,
    OracleSource,
    PerpMarketAccount,
    PoolBalance,
    SpotMarketAccount,
)
from driftpy.constants.config import devnet_spot_market_configs
from solders.pubkey import Pubkey

mock_pool_balance = PoolBalance(
    scaled_balance=0, market_index=0, padding=[0] * 6
)  # Replace with actual PoolBalance mock data
mock_fee_pool = PoolBalance(
    scaled_balance=0, market_index=0, padding=[0] * 6
)  # Replace with actual PoolBalance mock data
mock_insurance_claim = InsuranceClaim(
    revenue_withdraw_since_last_settle=0,
    max_revenue_withdraw_per_period=0,
    last_revenue_withdraw_ts=0,
    quote_settled_insurance=0,
    quote_max_insurance=0,
)

mock_insurance_fund = InsuranceFund(
    Pubkey.default(),
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
)

mock_historical_index_data = HistoricalIndexData(
    PRICE_PRECISION,
    PRICE_PRECISION,
    PRICE_PRECISION,
    PRICE_PRECISION,
    0,
)

mock_historical_oracle_data = HistoricalOracleData(
    last_oracle_price=0,
    last_oracle_conf=0,
    last_oracle_delay=0,
    last_oracle_price_twap=0,
    last_oracle_price_twap5min=0,
    last_oracle_price_twap_ts=0,
)
mock_revenue_pool = PoolBalance(scaled_balance=0, market_index=0, padding=[0] * 6)

mock_spot_fee_pool = PoolBalance(scaled_balance=0, market_index=0, padding=[0] * 6)

mock_amm = AMM(
    oracle=Pubkey.default,  # Replace with the default pubkey
    historical_oracle_data=mock_historical_oracle_data,
    base_asset_amount_per_lp=0,
    quote_asset_amount_per_lp=0,
    fee_pool=mock_fee_pool,
    base_asset_reserve=1 * BASE_PRECISION,
    quote_asset_reserve=12 * QUOTE_PRECISION * AMM_TO_QUOTE_PRECISION_RATIO,
    concentration_coef=0,
    min_base_asset_reserve=0,
    max_base_asset_reserve=0,
    sqrt_k=1,
    peg_multiplier=1,
    terminal_quote_asset_reserve=0,
    base_asset_amount_long=0,
    base_asset_amount_short=0,
    base_asset_amount_with_amm=0,
    base_asset_amount_with_unsettled_lp=0,
    max_open_interest=0,
    quote_asset_amount=0,
    quote_entry_amount_long=0,
    quote_entry_amount_short=0,
    quote_break_even_amount_long=0,
    quote_break_even_amount_short=0,
    user_lp_shares=0,
    last_funding_rate=0,
    last_funding_rate_long=0,
    last_funding_rate_short=0,
    last24h_avg_funding_rate=0,
    total_fee=0,
    total_mm_fee=0,
    total_exchange_fee=0,
    total_fee_minus_distributions=0,
    total_fee_withdrawn=0,
    total_liquidation_fee=0,
    cumulative_funding_rate_long=0,
    cumulative_funding_rate_short=0,
    total_social_loss=0,
    ask_base_asset_reserve=0,
    ask_quote_asset_reserve=0,
    bid_base_asset_reserve=0,
    bid_quote_asset_reserve=0,
    last_oracle_normalised_price=0,
    last_oracle_reserve_price_spread_pct=0,
    last_bid_price_twap=0,
    last_ask_price_twap=0,
    last_mark_price_twap=0,
    last_mark_price_twap5min=0,
    last_update_slot=0,
    last_oracle_conf_pct=0,
    net_revenue_since_last_funding=0,
    last_funding_rate_ts=0,
    funding_period=0,
    order_step_size=0,
    order_tick_size=1,
    min_order_size=0,
    max_position_size=0,
    volume24h=0,
    long_intensity_volume=0,
    short_intensity_volume=0,
    last_trade_ts=0,
    mark_std=0,
    oracle_std=0,
    last_mark_price_twap_ts=0,
    base_spread=0,
    max_spread=0,
    long_spread=0,
    short_spread=0,
    long_intensity_count=0,
    short_intensity_count=0,
    max_fill_reserve_fraction=0,
    max_slippage_ratio=1000000,
    curve_update_intensity=0,
    amm_jit_intensity=0,
    oracle_source=OracleSource.Pyth(),
    last_oracle_valid=True,
    target_base_asset_amount_per_lp=0,
    per_lp_base=0,
    padding1=0,
    padding2=0,
    total_fee_earned_per_lp=0,
    padding=[0] * 12,  # Padding with 12 zeros
)

# Mock Perp Markets
mock_perp_markets = [
    PerpMarketAccount(
        status=MarketStatus.Initialized(),
        name=[],
        contract_type=ContractType.Perpetual(),
        contract_tier=ContractTier.A(),
        expiry_ts=0,
        expiry_price=0,
        market_index=0,
        pubkey=Pubkey.default(),
        amm=mock_amm,
        number_of_users_with_base=0,
        number_of_users=0,
        margin_ratio_initial=2000,
        margin_ratio_maintenance=1000,
        next_fill_record_id=0,
        pnl_pool=mock_pool_balance,
        if_liquidation_fee=0,
        liquidator_fee=0,
        imf_factor=0,
        next_funding_rate_record_id=0,
        next_curve_record_id=0,
        unrealized_pnl_imf_factor=0,
        unrealized_pnl_max_imbalance=0,
        unrealized_pnl_initial_asset_weight=0,
        unrealized_pnl_maintenance_asset_weight=0,
        insurance_claim=mock_insurance_claim,
        quote_spot_market_index=0,
        fee_adjustment=0,
        padding1=0,
        padding=[0] * 46,
    ),
    PerpMarketAccount(
        status=MarketStatus.Initialized(),
        name=[],
        contract_type=ContractType.Perpetual(),
        contract_tier=ContractTier.A(),
        expiry_ts=0,
        expiry_price=0,
        market_index=1,
        pubkey=Pubkey.default(),
        amm=mock_amm,
        number_of_users_with_base=0,
        number_of_users=0,
        margin_ratio_initial=0,
        margin_ratio_maintenance=0,
        next_fill_record_id=0,
        pnl_pool=mock_pool_balance,
        if_liquidation_fee=0,
        liquidator_fee=0,
        imf_factor=0,
        next_funding_rate_record_id=0,
        next_curve_record_id=0,
        unrealized_pnl_imf_factor=0,
        unrealized_pnl_max_imbalance=0,
        unrealized_pnl_initial_asset_weight=0,
        unrealized_pnl_maintenance_asset_weight=0,
        insurance_claim=mock_insurance_claim,
        quote_spot_market_index=0,
        fee_adjustment=0,
        padding1=0,
        padding=[0] * 46,
    ),
    PerpMarketAccount(
        status=MarketStatus.Initialized(),
        name=[],
        contract_type=ContractType.Perpetual(),
        contract_tier=ContractTier.A(),
        expiry_ts=0,
        expiry_price=0,
        market_index=2,
        pubkey=Pubkey.default(),
        amm=mock_amm,
        number_of_users_with_base=0,
        number_of_users=0,
        margin_ratio_initial=0,
        margin_ratio_maintenance=0,
        next_fill_record_id=0,
        pnl_pool=mock_pool_balance,
        if_liquidation_fee=0,
        liquidator_fee=0,
        imf_factor=0,
        next_funding_rate_record_id=0,
        next_curve_record_id=0,
        unrealized_pnl_imf_factor=0,
        unrealized_pnl_max_imbalance=0,
        unrealized_pnl_initial_asset_weight=0,
        unrealized_pnl_maintenance_asset_weight=0,
        insurance_claim=mock_insurance_claim,
        quote_spot_market_index=0,
        fee_adjustment=0,
        padding1=0,
        padding=[0] * 46,
    ),
]

mock_spot_markets = [
    SpotMarketAccount(
        status=MarketStatus.Active(),
        asset_tier=AssetTier.COLLATERAL,
        name=[],
        max_token_deposits=1000000 * QUOTE_PRECISION,
        market_index=0,
        pubkey=Pubkey.default(),  # Replace with appropriate default public key
        mint=devnet_spot_market_configs[0].mint,  # Replace with actual mint
        vault=Pubkey.default(),
        min_order_size=0,
        max_position_size=0,
        revenue_pool=mock_revenue_pool,
        insurance_fund=mock_insurance_fund,
        if_liquidation_fee=0,
        liquidator_fee=0,
        decimals=6,
        optimal_utilization=0,
        optimal_borrow_rate=0,
        max_borrow_rate=0,
        cumulative_deposit_interest=SPOT_MARKET_CUMULATIVE_INTEREST_PRECISION,
        cumulative_borrow_interest=SPOT_MARKET_CUMULATIVE_INTEREST_PRECISION,
        total_social_loss=0,
        total_quote_social_loss=0,
        deposit_balance=0,
        borrow_balance=0,
        last_interest_ts=0,
        last_twap_ts=0,
        oracle=Pubkey.default(),
        initial_asset_weight=SPOT_MARKET_WEIGHT_PRECISION,
        maintenance_asset_weight=SPOT_MARKET_WEIGHT_PRECISION,
        initial_liability_weight=SPOT_MARKET_WEIGHT_PRECISION,
        maintenance_liability_weight=SPOT_MARKET_WEIGHT_PRECISION,
        scale_initial_asset_weight_start=0,
        imf_factor=0,
        withdraw_guard_threshold=0,
        deposit_token_twap=0,
        borrow_token_twap=0,
        utilization_twap=0,
        order_step_size=0,
        order_tick_size=0,
        next_fill_record_id=0,
        next_deposit_record_id=0,
        orders_enabled=True,
        spot_fee_pool=mock_spot_fee_pool,
        total_spot_fee=0,
        total_swap_fee=0,
        flash_loan_amount=0,
        flash_loan_initial_token_amount=0,
        oracle_source=OracleSource.Pyth(),
        historical_oracle_data=mock_historical_oracle_data,
        historical_index_data=mock_historical_index_data,
        padding1=[0] * 6,
        padding=[0] * 48,
        expiry_ts=0,
    ),
    SpotMarketAccount(
        status=MarketStatus.Active(),
        asset_tier=AssetTier.CROSS,
        name=[],
        max_token_deposits=100 * QUOTE_PRECISION,
        market_index=1,
        pubkey=Pubkey.default(),
        mint=devnet_spot_market_configs[1].mint,
        vault=Pubkey.default(),
        min_order_size=0,
        max_position_size=0,
        revenue_pool=mock_revenue_pool,
        insurance_fund=mock_insurance_fund,
        if_liquidation_fee=0,
        liquidator_fee=0,
        decimals=9,
        optimal_utilization=0,
        optimal_borrow_rate=0,
        max_borrow_rate=0,
        cumulative_deposit_interest=SPOT_MARKET_CUMULATIVE_INTEREST_PRECISION,
        cumulative_borrow_interest=SPOT_MARKET_CUMULATIVE_INTEREST_PRECISION,
        total_social_loss=0,
        total_quote_social_loss=0,
        deposit_balance=0,
        borrow_balance=0,
        last_interest_ts=0,
        last_twap_ts=0,
        oracle=Pubkey.default(),
        initial_asset_weight=SPOT_MARKET_WEIGHT_PRECISION,
        maintenance_asset_weight=SPOT_MARKET_WEIGHT_PRECISION,
        initial_liability_weight=SPOT_MARKET_WEIGHT_PRECISION,
        maintenance_liability_weight=SPOT_MARKET_WEIGHT_PRECISION,
        scale_initial_asset_weight_start=0,
        imf_factor=0,
        withdraw_guard_threshold=0,
        deposit_token_twap=0,
        borrow_token_twap=0,
        utilization_twap=0,
        order_step_size=0,
        order_tick_size=0,
        next_fill_record_id=0,
        next_deposit_record_id=0,
        orders_enabled=True,
        spot_fee_pool=mock_spot_fee_pool,
        total_spot_fee=0,
        total_swap_fee=0,
        flash_loan_amount=0,
        flash_loan_initial_token_amount=0,
        oracle_source=OracleSource.Pyth(),
        historical_oracle_data=mock_historical_oracle_data,
        historical_index_data=mock_historical_index_data,
        padding1=[0] * 6,
        padding=[0] * 48,
        expiry_ts=0,
    ),
    SpotMarketAccount(
        status=MarketStatus.Active(),
        asset_tier=AssetTier.PROTECTED,
        name=[],
        max_token_deposits=100 * QUOTE_PRECISION,
        market_index=2,
        pubkey=Pubkey.default(),
        mint=devnet_spot_market_configs[2].mint,
        vault=Pubkey.default(),
        min_order_size=0,
        max_position_size=0,
        revenue_pool=mock_revenue_pool,
        insurance_fund=mock_insurance_fund,
        if_liquidation_fee=0,
        liquidator_fee=0,
        decimals=6,
        optimal_utilization=0,
        optimal_borrow_rate=0,
        max_borrow_rate=0,
        cumulative_deposit_interest=SPOT_CUMULATIVE_INTEREST_PRECISION,
        cumulative_borrow_interest=SPOT_MARKET_CUMULATIVE_INTEREST_PRECISION,
        total_social_loss=0,
        total_quote_social_loss=0,
        deposit_balance=0,
        borrow_balance=0,
        last_interest_ts=0,
        last_twap_ts=0,
        oracle=Pubkey.default(),
        initial_asset_weight=SPOT_MARKET_WEIGHT_PRECISION,
        maintenance_asset_weight=SPOT_MARKET_WEIGHT_PRECISION,
        initial_liability_weight=SPOT_MARKET_WEIGHT_PRECISION,
        maintenance_liability_weight=SPOT_MARKET_WEIGHT_PRECISION,
        scale_initial_asset_weight_start=0,
        imf_factor=0,
        withdraw_guard_threshold=0,
        deposit_token_twap=0,
        borrow_token_twap=0,
        utilization_twap=0,
        order_step_size=0,
        order_tick_size=0,
        next_fill_record_id=0,
        next_deposit_record_id=0,
        orders_enabled=True,
        spot_fee_pool=mock_spot_fee_pool,
        total_spot_fee=0,
        total_swap_fee=0,
        flash_loan_amount=0,
        flash_loan_initial_token_amount=0,
        oracle_source=OracleSource.Pyth(),
        historical_oracle_data=mock_historical_oracle_data,
        historical_index_data=mock_historical_index_data,
        padding1=[0] * 6,
        padding=[0] * 48,
        expiry_ts=0,
    ),
]
