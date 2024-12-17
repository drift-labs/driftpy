from typing import Optional

from anchorpy import Context
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.system_program import ID
from solders.sysvar import RENT
from spl.token.constants import TOKEN_PROGRAM_ID

from driftpy.accounts import get_perp_market_account, get_state_account
from driftpy.addresses import *
from driftpy.constants.numeric_constants import (
    BASE_PRECISION,
    PEG_PRECISION,
    PRICE_PRECISION,
    SPOT_RATE_PRECISION,
    SPOT_WEIGHT_PRECISION,
)
from driftpy.drift_client import (
    DriftClient,
)
from driftpy.types import (
    AssetTier,
    ContractTier,
    OracleGuardRails,
    OracleSource,
    PrelaunchOracleParams,
)


class Admin(DriftClient):
    async def initialize(
        self,
        usdc_mint: Pubkey,
        admin_controls_prices: bool,
    ) -> tuple[Signature, Signature]:
        state_account_rpc_response = (
            await self.program.provider.connection.get_account_info(
                get_state_public_key(self.program_id)
            )
        )
        if state_account_rpc_response.value is not None:
            raise RuntimeError("Drift Client already initialized")

        state_public_key = get_state_public_key(self.program_id)

        initialize_tx_sig = await self.program.rpc["initialize"](
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": state_public_key,
                    "quote_asset_mint": usdc_mint,
                    "drift_signer": get_drift_client_signer_public_key(self.program_id),
                    "rent": RENT,
                    "system_program": ID,
                    "token_program": TOKEN_PROGRAM_ID,
                },
            ),
        )

        return initialize_tx_sig

    async def initialize_perp_market(
        self,
        market_index: int,
        price_oracle: Pubkey,
        base_asset_reserve: int,
        quote_asset_reserve: int,
        periodicity: int,
        peg_multiplier: int = PEG_PRECISION,
        oracle_source: OracleSource = OracleSource.Pyth(),
        contract_tier: ContractTier = ContractTier.Speculative(),
        margin_ratio_initial: int = 2000,
        margin_ratio_maintenance: int = 500,
        liquidator_fee: int = 0,
        if_liquidator_fee: int = 10000,
        imf_factor: int = 0,
        active_status: bool = True,
        base_spread: int = 0,
        max_spread: int = 142500,
        max_open_interest: int = 0,
        max_revenue_withdraw_per_period: int = 0,
        quote_max_insurance: int = 0,
        order_step_size: int = BASE_PRECISION // 10000,
        order_tick_size: int = PRICE_PRECISION // 100000,
        min_order_size: int = BASE_PRECISION // 10000,
        concentration_coef_scale: int = 1,
        curve_update_intensity: int = 0,
        amm_jit_intensity: int = 0,
        name: list = [0] * 32,
    ) -> Signature:
        state_public_key = get_state_public_key(self.program.program_id)
        state = await get_state_account(self.program)
        market_pubkey = get_perp_market_public_key(
            self.program.program_id,
            state.number_of_markets,
        )

        return await self.program.rpc["initialize_perp_market"](
            market_index,
            base_asset_reserve,
            quote_asset_reserve,
            periodicity,
            peg_multiplier,
            oracle_source,
            contract_tier,
            margin_ratio_initial,
            margin_ratio_maintenance,
            liquidator_fee,
            if_liquidator_fee,
            imf_factor,
            active_status,
            base_spread,
            max_spread,
            max_open_interest,
            max_revenue_withdraw_per_period,
            quote_max_insurance,
            order_step_size,
            order_tick_size,
            min_order_size,
            concentration_coef_scale,
            curve_update_intensity,
            amm_jit_intensity,
            name,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": state_public_key,
                    "oracle": price_oracle,
                    "perp_market": market_pubkey,
                    "rent": RENT,
                    "system_program": ID,
                }
            ),
        )

    async def initialize_spot_market(
        self,
        mint: Pubkey,
        optimal_utilization: int = SPOT_RATE_PRECISION // 2,
        optimal_rate: int = SPOT_RATE_PRECISION,
        max_rate: int = SPOT_RATE_PRECISION,
        oracle: Pubkey = Pubkey([0] * Pubkey.LENGTH),
        oracle_source: OracleSource = OracleSource.QuoteAsset(),
        initial_asset_weight: int = SPOT_WEIGHT_PRECISION,
        maintenance_asset_weight: int = SPOT_WEIGHT_PRECISION,
        initial_liability_weight: int = SPOT_WEIGHT_PRECISION,
        maintenance_liability_weight: int = SPOT_WEIGHT_PRECISION,
        imf_factor: int = 0,
        liquidator_fee: int = 0,
        if_liquidation_fee: int = 0,
        scale_initial_asset_weight_start: int = 0,
        withdraw_guard_threshold: int = 0,
        order_tick_size: int = 1,
        order_step_size: int = 1,
        if_total_factor: int = 0,
        asset_tier: AssetTier = AssetTier.COLLATERAL(),
        active_status: bool = True,
        name: list = [0] * 32,
    ):
        state_public_key = get_state_public_key(self.program_id)
        state = await get_state_account(self.program)
        spot_market_index = state.number_of_spot_markets

        spot_public_key = get_spot_market_public_key(self.program_id, spot_market_index)
        spot_vault_public_key = get_spot_market_vault_public_key(
            self.program_id, spot_market_index
        )
        insurance_vault_public_key = get_insurance_fund_vault_public_key(
            self.program_id, spot_market_index
        )

        return await self.program.rpc["initialize_spot_market"](
            optimal_utilization,
            optimal_rate,
            max_rate,
            oracle_source,
            initial_asset_weight,
            maintenance_asset_weight,
            initial_liability_weight,
            maintenance_liability_weight,
            imf_factor,
            liquidator_fee,
            if_liquidation_fee,
            active_status,
            asset_tier,
            scale_initial_asset_weight_start,
            withdraw_guard_threshold,
            order_tick_size,
            order_step_size,
            if_total_factor,
            name,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": state_public_key,
                    "spot_market": spot_public_key,
                    "spot_market_vault": spot_vault_public_key,
                    "insurance_fund_vault": insurance_vault_public_key,
                    "drift_signer": get_drift_client_signer_public_key(self.program_id),
                    "spot_market_mint": mint,
                    "oracle": oracle,
                    "rent": RENT,
                    "system_program": ID,
                    "token_program": TOKEN_PROGRAM_ID,
                }
            ),
        )

    async def update_perp_auction_duration(
        self,
        min_duration: int,
    ):
        return await self.program.rpc["update_perp_auction_duration"](
            min_duration,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                }
            ),
        )

    async def update_perp_market_curve_update_intensity(
        self,
        market_index: int,
        curve_update_intensity: int,
    ):
        assert curve_update_intensity >= 0 and curve_update_intensity <= 100
        market_public_key = get_perp_market_public_key(self.program_id, market_index)
        return await self.program.rpc["update_perp_market_curve_update_intensity"](
            curve_update_intensity,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "perp_market": market_public_key,
                }
            ),
        )

    async def update_perp_market_oracle(
        self, market_index: int, oracle: Pubkey, oracle_source: OracleSource
    ):
        return await self.program.rpc["update_perp_market_oracle"](
            oracle,
            oracle_source,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "perp_market": get_perp_market_public_key(
                        self.program_id, market_index
                    ),
                    "oracle": oracle,
                }
            ),
        )

    async def update_spot_market_oracle(
        self, market_index: int, oracle: Pubkey, oracle_source: OracleSource
    ):
        return await self.program.rpc["update_spot_market_oracle"](
            oracle,
            oracle_source,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "spot_market": get_spot_market_public_key(
                        self.program_id, market_index
                    ),
                    "oracle": oracle,
                }
            ),
        )

    async def update_perp_market_max_fill_reserve_fraction(
        self,
        market_index: int,
        max_fill_reserve_fraction: int,
    ):
        market_public_key = get_perp_market_public_key(self.program_id, market_index)
        return await self.program.rpc["update_perp_market_max_fill_reserve_fraction"](
            max_fill_reserve_fraction,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "perp_market": market_public_key,
                }
            ),
        )

    async def update_lp_cooldown_time(self, duration: int):
        return await self.program.rpc["update_lp_cooldown_time"](
            duration,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                }
            ),
        )

    async def update_lp_cooldown_time(self, duration: int):
        return await self.program.rpc["update_lp_cooldown_time"](
            duration,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                }
            ),
        )

    async def update_perp_market_concentration_scale(
        self,
        market_index: int,
        concentration_scale: int,
    ):
        market_public_key = get_perp_market_public_key(self.program_id, market_index)
        return await self.program.rpc["update_perp_market_concentration_scale"](
            concentration_scale,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "perp_market": market_public_key,
                }
            ),
        )

    async def update_perp_market_base_spread(
        self,
        market_index: int,
        base_spread: int,
    ):
        market_public_key = get_perp_market_public_key(self.program_id, market_index)
        return await self.program.rpc["update_perp_market_base_spread"](
            base_spread,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "perp_market": market_public_key,
                }
            ),
        )

    async def update_perp_market_max_spread(
        self,
        market_index: int,
        max_spread: int,
    ):
        market_public_key = get_perp_market_public_key(self.program_id, market_index)
        return await self.program.rpc["update_perp_market_max_spread"](
            max_spread,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "perp_market": market_public_key,
                }
            ),
        )

    async def update_perp_market_step_size_and_tick_size(
        self,
        market_index: int,
        step_size: int,
        tick_size: int,
    ):
        market_public_key = get_perp_market_public_key(self.program_id, market_index)
        return await self.program.rpc["update_perp_market_step_size_and_tick_size"](
            step_size,
            tick_size,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "perp_market": market_public_key,
                }
            ),
        )

    async def update_perp_market_max_imbalances(
        self,
        market_index,
        unrealized_max_imbalance,
        max_revenue_withdraw_per_period,
        quote_max_insurance,
    ):
        return await self.program.rpc["update_perp_market_max_imbalances"](
            unrealized_max_imbalance,
            max_revenue_withdraw_per_period,
            quote_max_insurance,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "admin": self.authority,
                    "perp_market": get_perp_market_public_key(
                        self.program_id, market_index
                    ),
                },
            ),
        )

    from driftpy.types import ContractTier

    async def update_perp_market_contract_tier(
        self, market_index: int, contract_type: ContractTier
    ):
        return await self.program.rpc["update_perp_market_contract_tier"](
            contract_type,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "admin": self.authority,
                    "perp_market": get_perp_market_public_key(
                        self.program_id, market_index
                    ),
                },
            ),
        )

    from driftpy.types import MarketStatus

    async def update_perp_market_status(
        self, market_index: int, market_status: MarketStatus
    ):
        return await self.program.rpc["update_perp_market_status"](
            market_status,
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "admin": self.authority,
                    "perp_market": get_perp_market_public_key(
                        self.program_id, market_index
                    ),
                },
            ),
        )

    async def settle_expired_market_pools_to_revenue_pool(
        self,
        market_index: int,
    ):
        return await self.send_ixs(
            [
                await self.get_settle_expired_market_pools_to_revenue_pool_ix(
                    market_index,
                )
            ]
        )

    async def get_settle_expired_market_pools_to_revenue_pool_ix(
        self,
        market_index: int,
    ):
        from driftpy.constants.numeric_constants import QUOTE_SPOT_MARKET_INDEX

        return self.program.instruction["settle_expired_market_pools_to_revenue_pool"](
            ctx=Context(
                accounts={
                    "state": self.get_state_public_key(),
                    "admin": self.authority,
                    "spot_market": get_spot_market_public_key(
                        self.program_id, QUOTE_SPOT_MARKET_INDEX
                    ),
                    "perp_market": get_perp_market_public_key(
                        self.program_id, market_index
                    ),
                },
            ),
        )

    async def update_spot_market_expiry(
        self,
        spot_market_index: int,
        expiry_ts: int,
    ):
        market_public_key = get_spot_market_public_key(
            self.program_id, spot_market_index
        )
        return await self.program.rpc["update_spot_market_expiry"](
            expiry_ts,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "spot_market": market_public_key,
                }
            ),
        )

    async def update_perp_market_expiry(
        self,
        market_index: int,
        expiry_ts: int,
    ):
        market_public_key = get_perp_market_public_key(self.program_id, market_index)
        return await self.program.rpc["update_perp_market_expiry"](
            expiry_ts,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "perp_market": market_public_key,
                }
            ),
        )

    async def update_oracle_guard_rails(self, oracle_guard_rails: OracleGuardRails):
        return await self.program.rpc["update_oracle_guard_rails"](
            oracle_guard_rails,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                }
            ),
        )

    async def update_withdraw_guard_threshold(
        self, spot_market_index: int, withdraw_guard_threshold: int
    ):
        return await self.program.rpc["update_withdraw_guard_threshold"](
            withdraw_guard_threshold,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "spot_market": get_spot_market_public_key(
                        self.program_id, spot_market_index
                    ),
                }
            ),
        )

    async def update_state_settlement_duration(self, settlement_duration: int):
        return await self.program.rpc["update_state_settlement_duration"](
            settlement_duration,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                }
            ),
        )

    async def update_update_insurance_fund_unstaking_period(
        self, spot_market_index: int, insurance_fund_unstaking_period: int
    ):
        return await self.program.rpc["update_insurance_fund_unstaking_period"](
            insurance_fund_unstaking_period,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "spot_market": get_spot_market_public_key(
                        self.program_id, spot_market_index
                    ),
                }
            ),
        )

    async def update_k(
        self,
        sqrt_k: int,
        perp_market_index: int,
    ):
        return await self.send_ixs(await self.update_k_ix(sqrt_k, perp_market_index))

    async def update_k_ix(
        self,
        sqrt_k: int,
        perp_market_index: int,
    ):
        market = await get_perp_market_account(self.program, perp_market_index)

        return self.program.instruction["update_k"](
            sqrt_k,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "perp_market": get_perp_market_public_key(
                        self.program_id, perp_market_index
                    ),
                    "oracle": market.amm.oracle,
                }
            ),
        )

    async def repeg_curve(
        self,
        peg: int,
        perp_market_index: int,
    ):
        return await self.send_ixs(await self.repeg_curve_ix(peg, perp_market_index))

    async def repeg_curve_ix(
        self,
        peg: int,
        perp_market_index: int,
    ):
        market = await get_perp_market_account(self.program, perp_market_index)

        return self.program.instruction["repeg_amm_curve"](
            peg,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "perp_market": get_perp_market_public_key(
                        self.program_id, perp_market_index
                    ),
                    "oracle": market.amm.oracle,
                }
            ),
        )

    async def update_initial_percent_to_liquidate(
        self, initial_percent_to_liquidate: int
    ) -> Signature:
        state_public_key = get_state_public_key(self.program.program_id)

        return await self.program.rpc["update_initial_pct_to_liquidate"](
            initial_percent_to_liquidate,
            ctx=Context(accounts={"admin": self.authority, "state": state_public_key}),
        )

    async def initialize_prelaunch_oracle(
        self,
        perp_market_index: int,
        price: Optional[int] = None,
        max_price: Optional[int] = None,
    ):
        params = PrelaunchOracleParams(perp_market_index, price, max_price)

        return await self.program.rpc["initialize_prelaunch_oracle"](
            params,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "prelaunch_oracle": get_prelaunch_oracle_public_key(
                        self.program_id, perp_market_index
                    ),
                    "rent": RENT,
                    "system_program": ID,
                }
            ),
        )

    async def update_prelaunch_oracle_params(
        self,
        perp_market_index: int,
        price: Optional[int] = None,
        max_price: Optional[int] = None,
    ):
        params = PrelaunchOracleParams(perp_market_index, price, max_price)

        return await self.program.rpc["update_prelaunch_oracle_params"](
            params,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "prelaunch_oracle": get_prelaunch_oracle_public_key(
                        self.program_id, perp_market_index
                    ),
                }
            ),
        )
