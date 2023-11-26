import base64
from typing import cast, Optional, Callable
from solders.pubkey import Pubkey
from anchorpy import Program, ProgramAccount
from solana.rpc.commitment import Commitment

from driftpy.types import *
from driftpy.addresses import *
from .types import DataAndSlot, T


async def get_account_data_and_slot(
    address: Pubkey,
    program: Program,
    commitment: Commitment = "processed",
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


async def get_state_account_and_slot(program: Program) -> DataAndSlot[StateAccount]:
    state_public_key = get_state_public_key(program.program_id)
    return await get_account_data_and_slot(state_public_key, program)


async def get_state_account(program: Program) -> StateAccount:
    return (await get_state_account_and_slot(program)).data


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
) -> DataAndSlot[UserAccount]:
    return await get_account_data_and_slot(user_public_key, program)


async def get_user_account(
    program: Program,
    user_public_key: Pubkey,
) -> UserAccount:
    return (await get_user_account_and_slot(program, user_public_key)).data


async def get_perp_market_account_and_slot(
    program: Program, market_index: int
) -> Optional[DataAndSlot[PerpMarketAccount]]:
    perp_market_public_key = get_perp_market_public_key(
        program.program_id, market_index
    )
    return await get_account_data_and_slot(perp_market_public_key, program)


async def get_perp_market_account(
    program: Program, market_index: int
) -> PerpMarketAccount:
    return (await get_perp_market_account_and_slot(program, market_index)).data


async def get_all_perp_market_accounts(program: Program) -> list[ProgramAccount]:
    return await program.account["PerpMarket"].all()


async def get_spot_market_account_and_slot(
    program: Program, spot_market_index: int
) -> DataAndSlot[SpotMarketAccount]:
    spot_market_public_key = get_spot_market_public_key(
        program.program_id, spot_market_index
    )
    return await get_account_data_and_slot(spot_market_public_key, program)


async def get_spot_market_account(
    program: Program, spot_market_index: int
) -> SpotMarketAccount:
    return (await get_spot_market_account_and_slot(program, spot_market_index)).data


async def get_all_spot_market_accounts(program: Program) -> list[ProgramAccount]:
    return await program.account["SpotMarket"].all()
