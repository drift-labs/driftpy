import asyncio
import base64
import json
import os
import pprint
import time
import urllib.parse

import requests
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient

from driftpy.constants.numeric_constants import BASE_PRECISION
from driftpy.drift_client import DriftClient
from driftpy.keypair import load_keypair
from driftpy.swift.util import digest_signature, generate_signed_msg_uuid
from driftpy.types import (
    MarketType,
    OrderParams,
    OrderTriggerCondition,
    OrderType,
    PositionDirection,
    PostOnlyParams,
    SignedMsgOrderParamsMessage,
    is_variant,
)

CONFIRM_TIMEOUT = 60


async def main():
    load_dotenv()
    RPC_URL = os.getenv("RPC_TRITON")
    PRIVATE_KEY = os.getenv("PRIVATE_KEY_2")
    connection = AsyncClient(RPC_URL)
    keypair = load_keypair(PRIVATE_KEY)

    drift_client: DriftClient = DriftClient(wallet=keypair, connection=connection)
    print("Subscribing to drift client...")
    await drift_client.subscribe()
    print("Subscribed")

    swift_url = "https://swift.drift.trade"

    market_index = 51  # 1KMEW-PERP

    oracle_price_data = drift_client.get_oracle_price_data_for_perp_market(market_index)
    low_price = int(oracle_price_data.price * BASE_PRECISION // 1e6)
    high_price = int(low_price * 101 // 100)

    perp_market = drift_client.get_perp_market_account(market_index)
    base_asset_amount = perp_market.amm.min_order_size * 2

    direction = PositionDirection.Short()

    order_params = OrderParams(
        market_index=market_index,
        order_type=OrderType.Market(),
        market_type=MarketType.Perp(),
        direction=direction,
        base_asset_amount=base_asset_amount,
        auction_start_price=low_price if is_variant(direction, "Long") else high_price,
        auction_end_price=high_price if is_variant(direction, "Long") else low_price,
        auction_duration=50,
        max_ts=None,
        user_order_id=0,
        price=0,
        oracle_price_offset=None,
        reduce_only=False,
        post_only=PostOnlyParams.NONE(),
        trigger_price=None,
        trigger_condition=OrderTriggerCondition.Above(),
    )

    taker_slot = (await connection.get_slot()).value
    swift_message = SignedMsgOrderParamsMessage(
        signed_msg_order_params=order_params,
        sub_account_id=drift_client.active_sub_account_id,
        slot=taker_slot,
        uuid=generate_signed_msg_uuid(),
        stop_loss_order_params=None,
        take_profit_order_params=None,
    )

    signed_msg = drift_client.sign_signed_msg_order_params_message(swift_message)
    message = signed_msg.order_params
    signature = signed_msg.signature

    hash = digest_signature(signature)
    encoded_hash = urllib.parse.quote(hash)
    print(f"Encoded Hash: {encoded_hash}")

    payload = {
        "market_index": market_index,
        "market_type": "perp",
        "message": message.decode("utf-8"),
        "signature": base64.b64encode(signature).decode("utf-8"),
        "taker_pubkey": str(drift_client.wallet.public_key),
    }
    pprint.pprint(payload)
    more_info = {
        "taker_order_params": str(order_params),
    }
    pprint.pprint(more_info)
    response = requests.post(
        f"{swift_url}/orders",
        json=payload,
        headers={"Content-Type": "application/json"},
    )
    print(f"Order response: {response.text}")

    expire_time = time.time() + CONFIRM_TIMEOUT
    while time.time() < expire_time:
        response = requests.get(
            f"{swift_url}/confirmation/hash-status?hash={encoded_hash}",
        )
        if response.status_code == 200:
            print(f"Order answered: {response.text}")
            print(f"Order hash: {encoded_hash}")
            break
        elif response.status_code == 404:
            print(f"Order not found: {response.text}")
        elif response.status_code >= 500:
            print(f"Error: {response.text}")
            break
        print("Waiting 3 seconds...")
        await asyncio.sleep(3)

    print("Finished")


if __name__ == "__main__":
    asyncio.run(main())
