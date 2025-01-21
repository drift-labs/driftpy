from typing import Callable, Optional, cast

from anchorpy.program.core import Program
from anchorpy.program.namespace.account import ProgramAccount
from solana.rpc.commitment import Commitment
from solders.pubkey import Pubkey

from driftpy.accounts.types import DataAndSlot, T
from driftpy.addresses import (
    get_insurance_fund_stake_public_key,
    get_perp_market_public_key,
    get_protected_maker_mode_config_public_key,
    get_spot_market_public_key,
    get_state_public_key,
    get_user_stats_account_public_key,
)
from driftpy.types import (
    InsuranceFundStakeAccount,
    PerpMarketAccount,
    SpotMarketAccount,
    StateAccount,
    UserAccount,
    UserStatsAccount,
)


async def get_account_data_and_slot(
    address: Pubkey,
    program: Program,
    commitment: Commitment = Commitment("processed"),
    decode: Optional[Callable[[bytes], T]] = None,
) -> Optional[DataAndSlot[T]]:
    try:
        resp = await program.provider.connection.get_account_info(
            address,
            encoding="base64",
            commitment=commitment,
        )
        if resp.value is None:
            # print(f"Account {address} not found")
            return None

        data = resp.value.data
        if len(data) == 0:
            print(f"resp: {resp}")
            print(f"value: {resp.value}")
            print(f"data: {data}")
            raise Exception(f"Account {address} has no data")

        slot = resp.context.slot
        decoded_data = (
            decode(data) if decode is not None else program.coder.accounts.decode(data)
        )

        return DataAndSlot(slot, decoded_data)
    except Exception as e:
        print(f"Error fetching account {address}: {str(e)}")
        raise


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
) -> Optional[DataAndSlot[UserAccount]]:
    return await get_account_data_and_slot(user_public_key, program)


async def get_user_account(
    program: Program,
    user_public_key: Pubkey,
) -> Optional[UserAccount]:
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
) -> Optional[PerpMarketAccount]:
    return (await get_perp_market_account_and_slot(program, market_index)).data


async def get_all_perp_market_accounts(program: Program) -> list[ProgramAccount]:
    return await program.account["PerpMarket"].all()


async def get_spot_market_account_and_slot(
    program: Program, spot_market_index: int
) -> Optional[DataAndSlot[SpotMarketAccount]]:
    spot_market_public_key = get_spot_market_public_key(
        program.program_id, spot_market_index
    )
    return await get_account_data_and_slot(spot_market_public_key, program)


async def get_spot_market_account(
    program: Program, spot_market_index: int
) -> Optional[SpotMarketAccount]:
    return (await get_spot_market_account_and_slot(program, spot_market_index)).data


async def get_all_spot_market_accounts(program: Program) -> list[ProgramAccount]:
    return await program.account["SpotMarket"].all()


async def get_protected_maker_mode_stats(program: Program) -> dict[str, int | bool]:
    config_pubkey = get_protected_maker_mode_config_public_key(program.program_id)
    config = await program.account["ProtectedMakerModeConfig"].fetch(config_pubkey)
    return {
        "max_users": config.max_users,
        "current_users": config.current_users,
        "is_reduce_only": config.reduce_only > 0,
    }
