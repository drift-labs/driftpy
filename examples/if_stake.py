import json
import os
import pprint
import sys

from solders.signature import Signature

from driftpy.addresses import get_insurance_fund_vault_public_key
from driftpy.types import TxParams

sys.path.append("../src/")

import argparse

from anchorpy.provider import Wallet
from solana.rpc import commitment
from solana.rpc.async_api import AsyncClient
from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import (
    create_associated_token_account,
    get_associated_token_address,
)

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.accounts import (
    get_if_stake_account,
    get_insurance_fund_stake_public_key,
    get_spot_market_account,
)
from driftpy.constants.numeric_constants import QUOTE_PRECISION
from driftpy.drift_client import DriftClient


async def view_logs(sig: Signature, connection: AsyncClient):
    connection._commitment = commitment.Confirmed
    logs = ""
    try:
        await connection.confirm_transaction(sig, commitment.Confirmed)
        logs_response = await connection.get_transaction(sig)
        if logs_response.value is None:
            raise Exception("No value found")
        if logs_response.value.transaction.meta is None:
            raise Exception("No logs found")
        logs = logs_response.value.transaction.meta.log_messages
    finally:
        connection._commitment = commitment.Processed
    pprint.pprint(logs)


async def does_account_exist(connection, address):
    rpc_resp = await connection.get_account_info(address)
    if rpc_resp["result"]["value"] is None:
        return False
    return True


async def main(
    keypath,
    env,
    url,
    spot_market_index,
    if_amount,
    operation,
):
    with open(keypath, "r") as f:
        secret = json.load(f)
    kp = Keypair.from_bytes(bytes(secret))
    print("using public key:", kp.pubkey())
    print("spot market:", spot_market_index)

    wallet = Wallet(kp)
    connection = AsyncClient(url)

    dc = DriftClient(
        connection,
        wallet,
        env,
        account_subscription=AccountSubscriptionConfig("websocket"),
    )
    dc.tx_params = TxParams(200_000, 10_000)

    print(dc.program_id)

    spot_market = await get_spot_market_account(dc.program, spot_market_index)
    if spot_market is None:
        raise Exception("No spot market found")
    spot_mint = spot_market.mint
    print(spot_mint)

    ata = get_associated_token_address(wallet.public_key, spot_mint)
    balance = await connection.get_token_account_balance(ata)
    if balance.value is None:
        raise Exception("No balance found")

    print("current spot ata balance:", balance.value.ui_amount)
    print("ATA addr:", ata)

    if operation == "add" or operation == "remove" and spot_market_index == 1:
        ata = get_associated_token_address(dc.authority, spot_market.mint)
        if not await does_account_exist(connection, ata):
            ix = create_associated_token_account(
                dc.authority, dc.authority, spot_market.mint
            )
            await dc.send_ixs(ix)

        # send to WSOL and sync
        # https://github.dev/solana-labs/solana-program-library/token/js/src/ix/types.ts
        keys = [
            AccountMeta(
                pubkey=dc.get_associated_token_account_public_key(spot_market_index),
                is_signer=False,
                is_writable=True,
            )
        ]
        data = int.to_bytes(17, 1, "little")
        program_id = TOKEN_PROGRAM_ID
        ix = Instruction(accounts=keys, program_id=program_id, data=data)
        await dc.send_ixs(ix)

    spot = await get_spot_market_account(dc.program, spot_market_index)
    if spot is None:
        raise Exception("No spot market found")
    total_shares = spot.insurance_fund.total_shares

    print(f"{operation}ing {if_amount}$ spot...")
    spot_percision = 10**spot.decimals
    if_amount = int(if_amount * spot_percision)

    if operation == "add":
        resp = input("confirm adding stake: Y?")
        if resp != "Y":
            print("confirmation failed exiting...")
            return

        if_addr = get_insurance_fund_stake_public_key(
            dc.program_id, kp.pubkey(), spot_market_index
        )
        if not await does_account_exist(connection, if_addr):
            print("initializing stake account...")
            sig = await dc.initialize_insurance_fund_stake(spot_market_index)
            print(sig)

        print("adding stake ....")
        sig = await dc.add_insurance_fund_stake(spot_market_index, if_amount)
        print(sig)

    elif operation == "cancel":
        print("canceling...")
        sig = await dc.cancel_request_remove_insurance_fund_stake(spot_market_index)
        print(sig)

    elif operation == "remove":
        resp = input("confirm removing stake: Y?")
        if resp != "Y":
            print("confirmation failed exiting...")
            return

        if if_amount is None:
            vault_pk = get_insurance_fund_vault_public_key(
                dc.program_id, spot_market_index
            )
            vault_balance = await connection.get_token_account_balance(vault_pk)
            if vault_balance.value is None:
                raise Exception("No vault balance found")

            vault_balance = vault_balance.value.ui_amount
            if vault_balance is None:
                raise Exception("No vault balance found")

            spot_market = await get_spot_market_account(dc.program, spot_market_index)
            if spot_market is None:
                raise Exception("No spot market found")

            ifstake = await get_if_stake_account(
                dc.program, dc.authority, spot_market_index
            )
            if ifstake is None:
                raise Exception("No if stake found")
            total_amount = (
                vault_balance
                * ifstake.if_shares
                / spot_market.insurance_fund.total_shares
            )

            spot_market = await get_spot_market_account(dc.program, spot_market_index)
            if spot_market is None:
                raise Exception("No spot market found")
            ifstake = await get_if_stake_account(
                dc.program, dc.authority, spot_market_index
            )
            total_amount = (
                vault_balance
                * ifstake.if_shares
                / spot_market.insurance_fund.total_shares
            )
            print(f"claimable amount: {total_amount}$")
            if_amount = int(total_amount * QUOTE_PRECISION)

        print("requesting to remove if stake...")
        ix = await dc.request_remove_insurance_fund_stake(spot_market_index, if_amount)
        await view_logs(ix, connection)

        print("removing if stake...")
        try:
            ix = await dc.remove_insurance_fund_stake(spot_market_index)
            await view_logs(ix, connection)
        except Exception as e:
            print(
                "unable to unstake -- likely bc not enough time has passed since request"
            )
            print(e)
            return

    elif operation == "view":
        if_stake = await get_if_stake_account(
            dc.program, dc.authority, spot_market_index
        )
        n_shares = if_stake.if_shares

        conn = dc.program.provider.connection
        vault_pk = get_insurance_fund_vault_public_key(dc.program_id, spot_market_index)
        v_amount = int((await conn.get_token_account_balance(vault_pk)).value.amount)
        balance = v_amount * n_shares / total_shares
        print(
            f"vault_amount: {v_amount/QUOTE_PRECISION:,.2f}$ \nn_shares: {n_shares} \ntotal_shares: {total_shares} \n>balance: {balance / QUOTE_PRECISION}"
        )

    elif operation == "settle":
        resp = input("confirm settling revenue to if stake: Y?")
        if resp != "Y":
            print("confirmation failed exiting...")
            return

        await dc.settle_revenue_to_insurance_fund(spot_market_index)

    else:
        return

    if operation in ["add", "remove"]:
        ifstake = await get_if_stake_account(
            dc.program, dc.authority, spot_market_index
        )
        print("total if shares:", ifstake.if_shares)

    print("done! :)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--keypath", type=str, required=False, default=os.environ.get("ANCHOR_WALLET")
    )
    parser.add_argument("--env", type=str, default="devnet")
    parser.add_argument("--amount", type=float, required=False)
    parser.add_argument("--market", type=int, required=True)
    parser.add_argument(
        "--operation",
        choices=["remove", "add", "view", "settle", "cancel"],
        required=True,
    )

    args = parser.parse_args()

    if args.operation == "add":
        assert args.amount is not None, "adding requires --amount"

    if args.operation == "remove" and args.amount is None:
        print("removing full IF stake")

    if args.keypath is None:
        raise NotImplementedError("need to provide keypath or set ANCHOR_WALLET")

    match args.env:
        case "devnet":
            url = "https://api.devnet.solana.com"
        case "mainnet":
            url = "https://api.mainnet-beta.solana.com"
        case _:
            raise NotImplementedError("only devnet/mainnet env supported")

    import asyncio

    asyncio.run(
        main(
            args.keypath,
            args.env,
            url,
            args.market,
            args.amount,
            args.operation,
        )
    )
