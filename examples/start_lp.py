import json
import pprint
import sys


sys.path.append("../src/")

from anchorpy import Wallet
from dotenv import load_dotenv
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.accounts import *
from driftpy.constants.config import configs
from driftpy.constants.numeric_constants import AMM_RESERVE_PRECISION
from driftpy.constants.numeric_constants import QUOTE_PRECISION
from driftpy.drift_client import DriftClient
from driftpy.keypair import load_keypair
from solana.rpc import commitment
from solana.rpc.async_api import AsyncClient


load_dotenv()


async def view_logs(sig: str, connection: AsyncClient):
    connection._commitment = commitment.Confirmed
    logs = ""
    try:
        await connection.confirm_transaction(sig, commitment.Confirmed)
        logs = (await connection.get_transaction(sig))["result"]["meta"]["logMessages"]
    finally:
        connection._commitment = commitment.Processed
    pprint.pprint(logs)


async def main(
    keypath,
    env,
    url,
    market_index,
    liquidity_amount,
    operation,
):
    kp = load_keypair(keypath)
    print("using public key:", kp.pubkey())
    print("market:", market_index)

    wallet = Wallet(kp)
    connection = AsyncClient(url)

    dc = DriftClient(
        connection,
        wallet,
        "mainnet",
        account_subscription=AccountSubscriptionConfig("websocket"),
    )
    dc.tx_params = TxParams(200_000, 10_000)

    await dc.subscribe()
    drift_user = dc.get_user()

    total_collateral = drift_user.get_total_collateral()
    print("total collateral:", total_collateral / QUOTE_PRECISION)

    if total_collateral == 0:
        print("cannot lp with 0 collateral")
        return

    market = await get_perp_market_account(dc.program, market_index)

    lp_amount = liquidity_amount * AMM_RESERVE_PRECISION
    lp_amount -= lp_amount % market.amm.order_step_size
    lp_amount = int(lp_amount)
    print("standardized lp amount:", lp_amount / AMM_RESERVE_PRECISION)

    if lp_amount < market.amm.order_step_size:
        print("lp amount too small - exiting...")

    print(f"{operation}ing {lp_amount} lp shares...")

    sig = None
    if operation == "add":
        resp = input("confirm adding liquidity? (Y/n)")
        if resp == "n":
            print("exiting...")
            return
        sig = await dc.add_liquidity(lp_amount, market_index)
        print(sig)

    elif operation == "remove":
        resp = input("confirm removing liquidity? (Y/n)")
        if resp == "n":
            print("exiting...")
            return
        sig = await dc.remove_liquidity(lp_amount, market_index)
        print(sig)

    elif operation == "view":
        pass

    elif operation == "settle":
        resp = input("confirm settling revenue to if stake? (Y/n)")
        if resp == "n":
            print("exiting...")
            return
        sig = await dc.settle_lp(dc.authority, market_index)
        print(sig)

    else:
        return

    if sig:
        print("confirming tx...")
        await connection.confirm_transaction(sig)

    position = dc.get_perp_position(market_index)
    market = await get_perp_market_account(dc.program, market_index)
    percent_provided = (position.lp_shares / market.amm.sqrt_k) * 100
    print(f"lp shares: {position.lp_shares}")
    print(f"providing {percent_provided}% of total market liquidity")
    print("done! :)")


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--keypath", type=str, required=False, default=os.environ.get("ANCHOR_WALLET")
    )
    parser.add_argument("--env", type=str, default="devnet")
    parser.add_argument("--amount", type=float, required=True)
    parser.add_argument("--market", type=int, required=True)
    parser.add_argument(
        "--operation", choices=["remove", "add", "view", "settle"], required=True
    )
    args = parser.parse_args()

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
