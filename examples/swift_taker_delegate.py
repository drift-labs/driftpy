import asyncio
import base64
import json
import os
import time
import urllib.parse

import requests
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

from driftpy.addresses import get_signed_msg_user_account_public_key
from driftpy.drift_client import DriftClient
from driftpy.keypair import load_keypair
from driftpy.slot.slot_subscriber import SlotSubscriber
from driftpy.swift.util import digest_signature, generate_signed_msg_uuid
from driftpy.types import (
    MarketType,
    OrderParams,
    OrderTriggerCondition,
    OrderType,
    PositionDirection,
    PostOnlyParams,
    SignedMsgOrderParamsDelegateMessage,
    is_variant,
)

load_dotenv()

CONFIRM_TIMEOUT = 60


async def main():
    RPC_URL = os.getenv("RPC_TRITON")
    DELEGATE_PRIVATE_KEY = os.getenv("PRIVATE_KEY_DELEGATE")

    delegate_keypair = load_keypair(DELEGATE_PRIVATE_KEY)
    target_authority = Pubkey.from_string(
        "Fe4hMZrg7R97ZrbSScWBXUpQwZB9gzBnhodTCGyjkHsG"
    )
    connection = AsyncClient(RPC_URL)

    drift_client: DriftClient = DriftClient(
        wallet=delegate_keypair,
        connection=connection,
        env="mainnet",
        sub_account_ids=[0],
        active_sub_account_id=0,
        authority=target_authority,
    )

    print("Target authority: ", target_authority)
    print("Using delegate keypair: ", str(delegate_keypair.pubkey()))

    print("Subscribing to drift client...")
    await drift_client.subscribe()
    print("Subscribed")

    if not str(drift_client.authority) == str(target_authority):
        raise Exception(
            "Target authority does not match the authority set in the drift client"
        )

    signed_msg_user_account = get_signed_msg_user_account_public_key(
        drift_client.program.program_id, target_authority
    )
    acc = await drift_client.connection.get_account_info(signed_msg_user_account)
    if acc is None:
        raise Exception("SignedMsgUserAccount does not exist")

    slot_subscriber = SlotSubscriber(drift_client)
    await slot_subscriber.subscribe()
    await asyncio.sleep(1)

    swift_url = "https://swift.drift.trade"
    market_index = 0
    direction = PositionDirection.Short()
    order_size = (
        drift_client.get_perp_market_account(market_index).amm.min_order_size * 2
    )

    slot = slot_subscriber.get_slot()
    print(f"Current slot: {slot}")
    oracle_info = drift_client.get_oracle_price_data_for_perp_market(market_index)

    high_price = oracle_info.price * 101 // 100
    low_price = oracle_info.price

    order_params = OrderParams(
        market_index=market_index,
        order_type=OrderType.Market(),
        market_type=MarketType.Perp(),
        direction=direction,
        base_asset_amount=order_size,
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

    # Use taker's public key but delegate's client to sign
    swift_message = SignedMsgOrderParamsDelegateMessage(
        signed_msg_order_params=order_params,
        slot=slot,
        uuid=generate_signed_msg_uuid(),
        stop_loss_order_params=None,
        take_profit_order_params=None,
        taker_pubkey=drift_client.get_user_account_public_key(),
    )

    # Sign with delegate's client
    signed_msg = drift_client.sign_signed_msg_order_params_message(
        swift_message, delegate_signer=True
    )
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
        "taker_pubkey": str(drift_client.authority),
        "signing_authority": str(drift_client.wallet.public_key),
    }

    print(f"DEBUG - Sending POST request to {swift_url}/orders")
    print(f"DEBUG - Payload: {json.dumps(payload, indent=2)}")

    response = requests.post(
        f"{swift_url}/orders",
        json=payload,
        headers={"Content-Type": "application/json"},
    )
    print(f"DEBUG - Response status code: {response.status_code}")
    print(f"Order response: {response.text}")

    expire_time = time.time() + CONFIRM_TIMEOUT
    while time.time() < expire_time:
        print(
            f"DEBUG - Sending GET request to {swift_url}/confirmation/hash-status?hash={encoded_hash}"
        )
        response = requests.get(
            f"{swift_url}/confirmation/hash-status?hash={encoded_hash}",
        )
        print(f"DEBUG - Response status code: {response.status_code}")
        print(f"DEBUG - Response headers: {dict(response.headers)}")

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
