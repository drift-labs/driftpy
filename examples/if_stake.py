import sys
import json
import pprint

sys.path.append("../src/")

from anchorpy import Wallet

from solders.keypair import Keypair  # type: ignore
from solders.instruction import Instruction  # type: ignore

from solana.rpc import commitment
from solana.rpc.async_api import AsyncClient
from solana.transaction import AccountMeta

from spl.token.instructions import get_associated_token_address
from spl.token.instructions import create_associated_token_account
from spl.token.constants import TOKEN_PROGRAM_ID

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.constants.config import configs
from driftpy.drift_client import DriftClient
from driftpy.accounts import *
from driftpy.constants.numeric_constants import QUOTE_PRECISION


async def view_logs(sig: str, connection: AsyncClient):
    connection._commitment = commitment.Confirmed
    logs = ""
    try:
        await connection.confirm_transaction(sig, commitment.Confirmed)
        logs = (await connection.get_transaction(sig))["result"]["meta"]["logMessages"]
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
    kp = Keypair.from_secret_key(bytes(secret))
    print("using public key:", kp.public_key)
    print("spot market:", spot_market_index)

    config = configs[env]
    wallet = Wallet(kp)
    connection = AsyncClient(url)

    dc = DriftClient(
        connection,
        wallet,
        config,
        account_subscription=AccountSubscriptionConfig("websocket"),
    )

    print(dc.program_id)

    spot_market = await get_spot_market_account(dc.program, spot_market_index)
    spot_mint = spot_market.mint
    print(spot_mint)

    ata = get_associated_token_address(wallet.public_key, spot_mint)
    balance = await connection.get_token_account_balance(ata)
    print("current spot ata balance:", balance["result"]["value"]["uiAmount"])
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
            dc.program_id, kp.public_key, spot_market_index
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
            vault_balance = (
                await connection.get_token_account_balance(
                    get_insurance_fund_vault_public_key(
                        dc.program_id, spot_market_index
                    )
                )
            )["result"]["value"]["uiAmount"]
            spot_market = await get_spot_market_account(dc.program, spot_market_index)
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
        v_amount = int(
            (await conn.get_token_account_balance(vault_pk))["result"]["value"][
                "amount"
            ]
        )
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
    import argparse
    import os

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
