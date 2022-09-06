from typing import Type
import asyncio

from solana.publickey import PublicKey
from solana.transaction import TransactionSignature
from solana.keypair import Keypair
from solana.system_program import SYS_PROGRAM_ID
from solana.sysvar import SYSVAR_RENT_PUBKEY
from spl.token.constants import TOKEN_PROGRAM_ID
from anchorpy import Program, Provider, Context

from driftpy.clearing_house import (
    ClearingHouse,
)
from driftpy.constants.numeric_constants import PEG_PRECISION
from driftpy.types import OracleSource
from driftpy.addresses import (
    get_market_public_key,
    get_bank_public_key,
    get_bank_vault_public_key,
    get_bank_vault_authority_public_key,
    get_state_public_key,
    get_user_account_public_key,
) 
from driftpy.accounts import ( 
    get_state_account
)
from driftpy.constants.numeric_constants import ( 
    BANK_INTEREST_PRECISION, 
    BANK_WEIGHT_PRECISION, 
)
from anchorpy import Wallet
from driftpy.constants.config import Config
from anchorpy import Provider, Idl
import driftpy
from pathlib import Path
import json

class Admin(ClearingHouse):

    @staticmethod
    def from_config(config: Config, provider: Provider, authority: Keypair = None, admin: bool = False):
        # read the idl 
        file = Path(str(driftpy.__path__[0]) + '/idl/clearing_house.json')
        with file.open() as f:
            idl_dict = json.load(f)
        idl = Idl.from_json(idl_dict)

        # create the program
        program = Program(
            idl, 
            config.clearing_house_program_id, 
            provider, 
        )

        clearing_house = Admin(program, authority)
        clearing_house.config = config
        clearing_house.idl = idl

        return clearing_house
    
    async def initialize(
        self, 
        usdc_mint: PublicKey,
        admin_controls_prices: bool,
    ) -> tuple[TransactionSignature, TransactionSignature]:

        state_account_rpc_response = await self.program.provider.connection.get_account_info(
            get_state_public_key(self.program_id)
        )
        if state_account_rpc_response["result"]["value"] is not None:
            raise RuntimeError("Clearing house already initialized")

        insurance_vault_public_key = PublicKey.find_program_address(
            [b"insurance_vault"],
            self.program_id
        )[0]

        insurance_vault_authority_public_key = PublicKey.find_program_address(
            [bytes(insurance_vault_public_key)],
            self.program_id
        )[0]

        state_public_key = get_state_public_key(self.program_id) 

        initialize_tx_sig = await self.program.rpc["initialize"](
            admin_controls_prices,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": state_public_key,
                    "quote_asset_mint": usdc_mint,
                    "insurance_vault": insurance_vault_public_key,
                    "insurance_vault_authority": insurance_vault_authority_public_key,
                    "rent": SYSVAR_RENT_PUBKEY,
                    "system_program": SYS_PROGRAM_ID,
                    "token_program": TOKEN_PROGRAM_ID,
                },
            ),
        )

        return initialize_tx_sig 

    async def initialize_market(
        self,
        price_oracle: PublicKey,
        base_asset_reserve: int,
        quote_asset_reserve: int,
        periodicity: int,
        peg_multiplier: int = PEG_PRECISION,
        oracle_source: OracleSource = OracleSource.PYTH(),
        margin_ratio_initial: int = 2000,
        margin_ratio_partial: int = 625,
        margin_ratio_maintenance: int = 500
    ) -> TransactionSignature:
        state_public_key = get_state_public_key(self.program.program_id)
        state = await get_state_account(self.program)
        market_pubkey = get_market_public_key(
            self.program.program_id,
            state.number_of_markets, 
        )

        return await self.program.rpc["initialize_market"](
            base_asset_reserve,
            quote_asset_reserve,
            periodicity,
            peg_multiplier,
            oracle_source,
            margin_ratio_initial,
            margin_ratio_partial,
            margin_ratio_maintenance,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": state_public_key,
                    "oracle": price_oracle,
                    "market": market_pubkey,
                    "rent": SYSVAR_RENT_PUBKEY, 
                    "system_program": SYS_PROGRAM_ID,
                }
            ),
        )
	
    async def initialize_bank(
        self,
		mint: PublicKey,
		optimal_utilization: int = BANK_INTEREST_PRECISION // 2,
		optimal_rate: int = BANK_INTEREST_PRECISION,
		max_rate: int = BANK_INTEREST_PRECISION,
		oracle: PublicKey = PublicKey([0] * PublicKey.LENGTH),
		oracle_source: OracleSource = OracleSource.QUOTE_ASSET(),
		initial_asset_weight: int = BANK_WEIGHT_PRECISION,
		maintenance_asset_weight: int = BANK_WEIGHT_PRECISION,
		initial_liability_weight: int = BANK_WEIGHT_PRECISION,
		maintenance_liability_weight: int = BANK_WEIGHT_PRECISION,
        imf_factor: int = 0,
        liquidation_fee: int = 0,
	):
        state_public_key = get_state_public_key(self.program_id)
        state = await get_state_account(self.program)
        bank_index = state.number_of_banks

        bank_public_key = get_bank_public_key(
            self.program_id,
            bank_index
        )
        bank_vault_public_key = get_bank_vault_public_key(
            self.program_id, 
            bank_index
        )
        bank_vault_authority_public_key = get_bank_vault_authority_public_key(
            self.program_id, 
            bank_index
        )

        return await self.program.rpc["initialize_bank"](
            optimal_utilization,
            optimal_rate,
            max_rate,
            oracle_source,
            initial_asset_weight,
            maintenance_asset_weight,
            initial_liability_weight,
            maintenance_liability_weight,
            imf_factor,
            liquidation_fee,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": state_public_key,
                    "bank": bank_public_key,
                    "bank_vault": bank_vault_public_key,
                    "bank_vault_authority": bank_vault_authority_public_key,
                    "bank_mint": mint,
                    "oracle": oracle,
                    "rent": SYSVAR_RENT_PUBKEY, 
                    "system_program": SYS_PROGRAM_ID,
                    "token_program": TOKEN_PROGRAM_ID,
                }
            )
        )

    async def update_auction_duration(
        self, 
        min_duration: int, 
        max_duration: int, 
    ): 
        return await self.program.rpc["update_auction_duration"](
            min_duration, 
            max_duration,
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                }
            )
        )

    async def update_max_base_asset_amount_ratio(
        self, 
        max_base_asset_amount_ratio: int, 
        market_index: int
    ): 
        market_public_key = get_market_public_key(
            self.program_id, 
            market_index
        )
        return await self.program.rpc["update_max_base_asset_amount_ratio"](
            max_base_asset_amount_ratio, 
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "market": market_public_key
                }
            )
        )
    
    async def update_lp_cooldown_time(
        self, 
        duration: int, 
        market_index: int
    ): 
        market_public_key = get_market_public_key(
            self.program_id, 
            market_index
        )
        return await self.program.rpc["update_lp_cooldown_time"](
            duration, 
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "market": market_public_key
                }
            )
        )

    async def update_market_base_spread(
        self,
        base_spread: int,
        market_index: int,
    ):
        market_public_key = get_market_public_key(
            self.program_id, 
            market_index
        )
        return await self.program.rpc["update_market_base_spread"](
            base_spread, 
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "market": market_public_key
                }
            )
        )

    async def update_market_base_asset_amount_step_size(
        self,
        step_size: int,
        market_index: int,
    ):
        market_public_key = get_market_public_key(
            self.program_id, 
            market_index
        )
        return await self.program.rpc["update_market_base_asset_amount_step_size"](
            step_size, 
            ctx=Context(
                accounts={
                    "admin": self.authority,
                    "state": get_state_public_key(self.program_id),
                    "market": market_public_key
                }
            )
        )