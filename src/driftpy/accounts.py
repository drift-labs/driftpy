from dataclasses import dataclass
import json
from importlib import resources
from typing import Optional, TypeVar, Type, cast
from solana.publickey import PublicKey
from solana.keypair import Keypair
from solana.transaction import Transaction, TransactionSignature, TransactionInstruction
from solana.system_program import SYS_PROGRAM_ID
from solana.sysvar import SYSVAR_RENT_PUBKEY
from solana.transaction import AccountMeta
from spl.token.constants import TOKEN_PROGRAM_ID
from anchorpy import Program, Context, Idl

from driftpy.types import (
    PriceDivergence,
    Validity,
    OracleGuardRails,
    DiscountTokenTier,
    DiscountTokenTiers,
    ReferralDiscount,
    OrderFillerRewardStructure,
    FeeStructure,
    StateAccount,
    OracleSource,
    DepositDirection,
    TradeDirection,
    OrderType,
    OrderStatus,
    OrderDiscountTier,
    OrderTriggerCondition,
    OrderAction,
    PositionDirection,
    SwapDirection,
    AssetType,
    BankBalanceType,
    Order,
    OrderParamsOptionalAccounts,
    OrderParams,
    OrderFillerRewardStructure,
    MarketPosition,
    UserFees,
    UserBankBalance,
    User,
    PoolBalance,
    Bank,
    AMM,
    Market,
)

from driftpy.program import load_program

from driftpy.addresses import (
    get_market_public_key,
    get_bank_public_key,
    get_bank_vault_public_key,
    get_bank_vault_authority_public_key,
    get_state_public_key,
    get_user_account_public_key,
) 

async def get_state_account(
    program: Program
) -> StateAccount:
    state_public_key = get_state_public_key(program.program_id)
    response = await program.account["State"].fetch(state_public_key)
    return cast(StateAccount, response)

async def get_user_account(
    program: Program, 
    authority: PublicKey,
    user_id: int = 0,
) -> User:
    user_public_key = get_user_account_public_key(
        program.program_id, 
        authority,
        user_id
    )
    response = await program.account["User"].fetch(user_public_key)
    return cast(User, response)

async def get_market_account(
    program: Program, 
    market_index: int
) -> Market:
    market_public_key = get_market_public_key(
        program.program_id, 
        market_index
    )
    response = await program.account["Market"].fetch(market_public_key)
    return cast(Market, response)

async def get_bank_account(
    program: Program, 
    bank_index: int
) -> Bank:
    bank_public_key = get_bank_public_key(
        program.program_id, 
        bank_index
    )
    response = await program.account["Bank"].fetch(bank_public_key)
    return cast(Bank, response)
