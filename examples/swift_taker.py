import asyncio
import base64
import json
import os
import time
import urllib.parse

import requests
from solana.rpc.async_api import AsyncClient

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
    RPC_URL = os.getenv("RPC_TRITON")
    PRIVATE_KEY = os.getenv("PRIVATE_KEY")
    connection = AsyncClient(RPC_URL)
    keypair = load_keypair(PRIVATE_KEY)

    drift_client = DriftClient(wallet=keypair, connection=connection)
    print("Subscribing to drift client...")
    await drift_client.subscribe()
    print("Subscribed")

    swift_url = "https://swift.drift.trade"

    slot_response = json.loads((await drift_client.connection.get_slot()).to_json())
    slot = slot_response["result"]
    market_index = 0
    oracle_info = drift_client.get_oracle_price_data_for_perp_market(market_index)

    high_price = oracle_info.price * 101 // 100
    low_price = oracle_info.price

    perp_market = drift_client.get_perp_market_account(market_index)
    base_asset_amount = perp_market.amm.min_order_size * 2

    direction = PositionDirection.Short()

    order_params = OrderParams(
        market_index=market_index,
        order_type=OrderType.Market(),
        market_type=MarketType.Perp(),
        direction=direction,
        base_asset_amount=base_asset_amount,
        auction_start_price=low_price if is_variant(direction, "short") else high_price,
        auction_end_price=high_price if is_variant(direction, "short") else low_price,
        auction_duration=50,
        max_ts=None,
        user_order_id=0,
        price=0,
        oracle_price_offset=None,
        reduce_only=False,
        post_only=PostOnlyParams.NONE(),
        immediate_or_cancel=False,
        trigger_price=None,
        trigger_condition=OrderTriggerCondition.Above(),
    )

    swift_message = SignedMsgOrderParamsMessage(
        signed_msg_order_params=order_params,
        sub_account_id=drift_client.active_sub_account_id,
        slot=slot,
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
        print("Waiting 10 seconds...")
        await asyncio.sleep(10)

    print("Finished")


if __name__ == "__main__":
    asyncio.run(main())
