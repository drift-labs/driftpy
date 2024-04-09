'''
This example demonstrates how to use place_and_take for perp and spot markets.

Set variables in `main()` to change order params.

python3 examples/place_and_take.py
'''
import os
import json
import time
import sys
import asyncio

from driftpy.keypair import load_keypair

sys.path.append("../src/")

from anchorpy import Wallet

from solders.keypair import Keypair  # type: ignore

from solana.rpc.async_api import AsyncClient

from driftpy.constants.config import configs, get_markets_and_oracles
from driftpy.types import MarketType, OrderType, OrderParams, PositionDirection, TxParams
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.accounts import get_perp_market_account, get_spot_market_account
from driftpy.accounts.oracle import get_oracle_price_data_and_slot
from driftpy.math.spot_market import get_signed_token_amount, get_token_amount
from driftpy.drift_client import DriftClient
from driftpy.constants.numeric_constants import BASE_PRECISION, PRICE_PRECISION

async def do_place_and_take(drift_client, market_type: MarketType, market_index: int):
    drift_client.get_place_and_take_perp_order_ix(order_params)


async def main():
    secret = os.getenv("PRIVATE_KEY")
    url = os.getenv("RPC_URL")

    sub_account_id = 1
    perp_market_index = 0 # SOL-PERP
    spot_market_index = 0 # SOL-PERP

    perp_

    kp = load_keypair(secret)
    wallet = Wallet(kp)
    connection = AsyncClient(url)

    drift_client = DriftClient(
        connection,
        wallet,
        "mainnet",
        account_subscription=AccountSubscriptionConfig("websocket"),
        tx_params=TxParams(300_000, 100_000),
        sub_account_ids=[sub_account_id],
        active_sub_account_id=sub_account_id
    )
    await drift_client.subscribe()
    user_account = drift_client.get_user_account()
    user = drift_client.get_user()
    user_states = drift_client.get_user_st

    print(f"Placing orders under authority:   {user_account.authority}")
    print(f"Placing orders under userAccount: {drift_client.get_user_account_public_key()}, subaccount_id: {user_account.sub_account_id}")

    oracle_price = await drift_client.get_oracle_price_data_for_perp_market(0)
    if oracle_price is None:
        raise Exception("Failed to get oracle price")
    print(f"Perp market oracle price: {oracle_price.price / PRICE_PRECISION}")


    drift_client.get_place_and_take_perp_order_ix(
        OrderParams(
            order_type=OrderType.Limit,
            base_asset_amount=1 * BASE_PRECISION,
            market_type=MarketType.Perp,
            market_index=perp_market_index,
            direction=PositionDirection.Long,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
    print("done")