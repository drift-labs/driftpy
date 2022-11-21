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

from driftpy.types import *
from driftpy.addresses import *


async def get_state_account(program: Program) -> State:
    state_public_key = get_state_public_key(program.program_id)
    response = await program.account["State"].fetch(state_public_key)
    return cast(State, response)


async def get_if_stake_account(
    program: Program, authority: PublicKey, spot_market_index: int
) -> InsuranceFundStake:
    if_stake_pk = get_insurance_fund_stake_public_key(
        program.program_id, authority, spot_market_index
    )
    response = await program.account["InsuranceFundStake"].fetch(if_stake_pk)
    return cast(InsuranceFundStake, response)


async def get_user_stats_account(
    program: Program,
    authority: PublicKey,
) -> UserStats:
    user_stats_public_key = get_user_stats_account_public_key(
        program.program_id,
        authority,
    )
    response = await program.account["UserStats"].fetch(user_stats_public_key)
    return cast(UserStats, response)


async def get_user_account(
    program: Program,
    authority: PublicKey,
    subaccount_id: int = 0,
) -> User:
    user_public_key = get_user_account_public_key(
        program.program_id, authority, subaccount_id
    )
    response = await program.account["User"].fetch(user_public_key)
    return cast(User, response)


async def get_perp_market_account(program: Program, market_index: int) -> PerpMarket:
    market_public_key = get_perp_market_public_key(program.program_id, market_index)
    response = await program.account["PerpMarket"].fetch(market_public_key)
    return cast(PerpMarket, response)


async def get_spot_market_account(
    program: Program, spot_market_index: int
) -> SpotMarket:
    spot_market_public_key = get_spot_market_public_key(
        program.program_id, spot_market_index
    )
    response = await program.account["SpotMarket"].fetch(spot_market_public_key)
    return cast(SpotMarket, response)
