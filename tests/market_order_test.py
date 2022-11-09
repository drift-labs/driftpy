import pytest
import math

import anchorpy
import pytest_asyncio
import solana.keypair
import solana.rpc.commitment

import driftpy.admin
import driftpy.constants.numeric_constants
import driftpy.setup.helpers
import driftpy.types
import driftpy.accounts

from _fixtures import *


@pytest.mark.asyncio
async def test_open_close_position(
    clearing_house: driftpy.admin.Admin,
    initialized_spot_market,
    initialized_market,
    user_usdc_account,
):

    await clearing_house.intialize_user()

    clearing_house.spot_market_atas[0] = user_usdc_account.public_key
    await clearing_house.deposit(
        USDC_AMOUNT, 
        0, 
        user_usdc_account.public_key, 
        user_initialized=True
    )
    await clearing_house.update_perp_auction_duration(
        0
    )

    baa = 10 * driftpy.constants.numeric_constants.AMM_RESERVE_PRECISION
    sig = await clearing_house.open_position(
        driftpy.types.PositionDirection.LONG(), 
        baa, 
        0,
    )

    clearing_house.program.provider.connection._commitment = solana.rpc.commitment.Confirmed
    tx = await clearing_house.program.provider.connection.get_transaction(sig)
    clearing_house.program.provider.connection._commitment = solana.rpc.commitment.Processed
    # print(tx)
    
    user_account = await driftpy.accounts.get_user_account(
        clearing_house.program, 
        clearing_house.authority
    )

    assert user_account.perp_positions[0].base_asset_amount == baa
    assert user_account.perp_positions[0].quote_asset_amount < 0

    await clearing_house.close_position(
        0
    )

    user_account = await driftpy.accounts.get_user_account(
        clearing_house.program, 
        clearing_house.authority
    )
    assert user_account.perp_positions[0].base_asset_amount == 0
    assert user_account.perp_positions[0].quote_asset_amount < 0