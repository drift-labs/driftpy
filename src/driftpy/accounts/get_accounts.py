import asyncio

from typing import cast, Optional, Callable


from anchorpy import Program, ProgramAccount

from solders.pubkey import Pubkey  # type: ignore

from solana.rpc.commitment import Commitment, Processed

from driftpy.addresses import *
from driftpy.types import *
from .types import DataAndSlot, T


async def get_account_data_and_slot(
    address: Pubkey,
    program: Program,
    commitment: Commitment = Processed,
    decode: Optional[Callable[[bytes], T]] = None,
) -> Optional[DataAndSlot[T]]:
    account_info = await program.provider.connection.get_account_info(
        address,
        encoding="base64",
        commitment=commitment,
    )

    if not account_info.value:
        return None

    slot = account_info.context.slot
    data = account_info.value.data

    decoded_data = (
        decode(data) if decode is not None else program.coder.accounts.decode(data)
    )

    return DataAndSlot(slot, decoded_data)


async def get_account_data_and_slot_with_retry(
    address: Pubkey,
    program: Program,
    commitment: Commitment = Processed,
    decode: Optional[Callable[[bytes], T]] = None,
    max_retries: int = 3,
    initial_delay: float = 1.0,
) -> Optional[DataAndSlot[T]]:
    retries = max_retries
    delay = initial_delay
    while retries > 0:
        result = await get_account_data_and_slot(address, program, commitment, decode)
        if result:
            return result
        await asyncio.sleep(delay)
        delay *= 2
        retries -= 1
    return None


async def get_state_account_and_slot(
    program: Program,
) -> Optional[DataAndSlot[StateAccount]]:
    state_public_key = get_state_public_key(program.program_id)
    return await get_account_data_and_slot_with_retry(state_public_key, program)


async def get_state_account(program: Program) -> Optional[StateAccount]:
    state_account = await get_account_data_and_slot(program)
    return getattr(state_account, "data", None)


async def get_if_stake_account(
    program: Program, authority: Pubkey, spot_market_index: int
) -> InsuranceFundStakeAccount:
    if_stake_pk = get_insurance_fund_stake_public_key(
        program.program_id, authority, spot_market_index
    )
    response = await program.account["InsuranceFundStake"].fetch(if_stake_pk)
    return cast(InsuranceFundStakeAccount, response)


async def get_user_stats_account(
    program: Program,
    authority: Pubkey,
) -> UserStatsAccount:
    user_stats_public_key = get_user_stats_account_public_key(
        program.program_id,
        authority,
    )
    response = await program.account["UserStats"].fetch(user_stats_public_key)
    return cast(UserStatsAccount, response)


async def get_user_account_and_slot(
    program: Program,
    user_public_key: Pubkey,
) -> Optional[DataAndSlot[UserAccount]]:
    return await get_account_data_and_slot_with_retry(user_public_key, program)


async def get_user_account(
    program: Program,
    user_public_key: Pubkey,
) -> Optional[UserAccount]:
    user_account = await get_user_account_and_slot(program, user_public_key)
    return getattr(user_account, "data", None)


async def get_perp_market_account_and_slot(
    program: Program, market_index: int
) -> Optional[DataAndSlot[PerpMarketAccount]]:
    perp_market_public_key = get_perp_market_public_key(
        program.program_id, market_index
    )
    return await get_account_data_and_slot_with_retry(perp_market_public_key, program)


async def get_perp_market_account(
    program: Program, market_index: int
) -> Optional[PerpMarketAccount]:
    perp_market = await get_perp_market_account_and_slot(program, market_index)
    return getattr(perp_market, "data", None)


async def get_all_perp_market_accounts(program: Program) -> list[ProgramAccount]:
    return await program.account["PerpMarket"].all()


async def get_spot_market_account_and_slot(
    program: Program, spot_market_index: int
) -> Optional[DataAndSlot[SpotMarketAccount]]:
    spot_market_public_key = get_spot_market_public_key(
        program.program_id, spot_market_index
    )
    return await get_account_data_and_slot_with_retry(spot_market_public_key, program)


async def get_spot_market_account(
    program: Program, spot_market_index: int
) -> Optional[SpotMarketAccount]:
    spot_market = await get_spot_market_account_and_slot(program, spot_market_index)
    return getattr(spot_market, "data", None)


async def get_all_spot_market_accounts(program: Program) -> list[ProgramAccount]:
    return await program.account["SpotMarket"].all()
