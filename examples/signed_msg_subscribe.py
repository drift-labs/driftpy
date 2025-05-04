import asyncio
import base64
import os
from functools import partial

from anchorpy.provider import Provider, Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solders.pubkey import Pubkey

from driftpy.accounts import get_user_stats_account_public_key
from driftpy.addresses import get_user_account_public_key
from driftpy.constants.numeric_constants import BASE_PRECISION, PRICE_PRECISION
from driftpy.drift_client import DriftClient
from driftpy.keypair import load_keypair
from driftpy.swift.order_subscriber import (
    SignedMsgOrderParamsMessage,
    SwiftOrderSubscriber,
    SwiftOrderSubscriberConfig,
)
from driftpy.types import (
    MarketType,
    OrderParams,
    OrderTriggerCondition,
    OrderType,
    PositionDirection,
    PostOnlyParams,
    is_variant,
)
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import PollingConfig, UserMapConfig


def convert_to_number(value: int, precision: int) -> float:
    if precision == 0:
        return float(value)
    return float(value / precision)


async def handle_order_log_only(
    order,
    signed_msg,
    drift_client: DriftClient,
):
    print()
    print("==> Received Order (Logging Only)")
    taker_authority = Pubkey.from_string(order["taker_authority"])

    if hasattr(signed_msg, "taker_pubkey"):
        taker_user_pubkey = signed_msg.taker_pubkey
        order_params = signed_msg.signed_msg_order_params
        print("Processing Delegate Message")
    elif hasattr(signed_msg, "sub_account_id"):
        order_params = signed_msg.signed_msg_order_params
        sub_account_id = signed_msg.sub_account_id
        taker_user_pubkey = get_user_account_public_key(
            drift_client.program.program_id, taker_authority, sub_account_id
        )
        print("Processing Standard Message")
    else:
        print(f"Unknown message structure: {signed_msg}")
        return

    direction_str = "Long" if is_variant(order_params.direction, "Long") else "Short"

    print(
        f"Taker ({taker_user_pubkey}) wants to {direction_str} "
        f"{convert_to_number(order_params.base_asset_amount, BASE_PRECISION)} units of market index {order_params.market_index}"
    )

    if order_params.auction_duration > 0:
        print(
            f"Auction params: Duration={order_params.auction_duration} slots. "
            f"Start Price={convert_to_number(order_params.auction_start_price, PRICE_PRECISION)}. "
            f"End Price={convert_to_number(order_params.auction_end_price, PRICE_PRECISION)}"
        )
    else:
        print("Not an auction order.")
    print("<==")


async def handle_and_fill_order(
    order_message_raw: dict,
    signed_message: SignedMsgOrderParamsMessage,
    drift_client: DriftClient,
    user_map: UserMap,
):
    print()
    print("==> Attempting to Fill Order")
    try:
        signed_msg_order_params_buf = bytes.fromhex(order_message_raw["order_message"])
        taker_signature = base64.b64decode(order_message_raw["order_signature"])
        taker_authority = Pubkey.from_string(order_message_raw["taker_authority"])
        signing_authority = Pubkey.from_string(
            order_message_raw.get("signing_authority", str(taker_authority))
        )
        order_uuid = order_message_raw["uuid"].encode("utf-8")

        if hasattr(signed_message, "taker_pubkey"):
            taker_order_params = signed_message.signed_msg_order_params
            taker_user_pubkey = signed_message.taker_pubkey
            is_delegate = True
            print("Processing Delegate Fill")
        elif hasattr(signed_message, "sub_account_id"):
            taker_order_params = signed_message.signed_msg_order_params
            sub_account_id = signed_message.sub_account_id
            taker_user_pubkey = get_user_account_public_key(
                drift_client.program.program_id, taker_authority, sub_account_id
            )
            is_delegate = False
            print("Processing Standard Fill")
        else:
            print(f"Unknown message structure for fill: {signed_message}")
            return

        taker_user_account = (
            await user_map.must_get(str(taker_user_pubkey))
        ).get_user_account()
        taker_stats_pubkey = get_user_stats_account_public_key(
            drift_client.program.program_id, taker_user_account.authority
        )

        is_taker_long = is_variant(taker_order_params.direction, "Long")
        maker_direction = (
            PositionDirection.Short() if is_taker_long else PositionDirection.Long()
        )

        if taker_order_params.auction_duration > 0:
            maker_price = (
                int(taker_order_params.auction_start_price * 0.99)
                if is_taker_long
                else int(taker_order_params.auction_end_price * 1.01)
            )
            print(f"Auction detected. Maker Price: {maker_price}")
        elif taker_order_params.price > 0:
            maker_price = taker_order_params.price
            print(f"Limit order detected. Maker Price: {maker_price}")
        else:
            print("Cannot determine maker price. Skipping fill.")
            return

        maker_order_params = OrderParams(
            market_index=taker_order_params.market_index,
            order_type=OrderType.Limit(),
            market_type=MarketType.Perp(),
            direction=maker_direction,
            base_asset_amount=taker_order_params.base_asset_amount,
            price=maker_price,
            post_only=PostOnlyParams.MustPostOnly(),
            user_order_id=0,
            reduce_only=False,
            trigger_price=0,
            trigger_condition=OrderTriggerCondition.Above(),
            auction_start_price=0,
            auction_end_price=0,
            auction_duration=0,
            max_ts=None,
            oracle_price_offset=None,
        )

        taker_info = {
            "taker": taker_user_pubkey,
            "taker_user_account": taker_user_account,
            "taker_stats": taker_stats_pubkey,
            "signing_authority": signing_authority,
        }

        preceding_ixs = []

        print(
            f"Constructing place_and_make IXs for market {maker_order_params.market_index}"
        )
        ixs = await drift_client.get_place_and_make_signed_msg_perp_order_ixs(
            signed_msg_order_params={
                "order_params": signed_msg_order_params_buf,
                "signature": taker_signature,
            },
            signed_msg_order_uuid=order_uuid,
            taker_info=taker_info,
            order_params=maker_order_params,
            preceding_ixs=preceding_ixs,
        )

        print(f"Successfully generated {len(ixs)} instructions:")
        for i, ix in enumerate(ixs):
            print(f"  Ix {i}: {ix}")

    except Exception as e:
        print(f"Error handling and filling order: {e}", exc_info=True)
    finally:
        print("<==")


async def main():
    print("Starting main function")
    load_dotenv()
    priv_key_str = os.getenv("PRIVATE_KEY")
    if priv_key_str is None:
        raise ValueError("Set PRIVATE_KEY in .env file")

    keypair = load_keypair(priv_key_str)
    rpc_triton = os.getenv("RPC_TRITON")
    if rpc_triton is None:
        raise ValueError("Set RPC_TRITON in .env file")

    connection = AsyncClient(rpc_triton, commitment=Commitment("confirmed"))
    print(f"RPC Endpoint: {connection._provider.endpoint_uri}")
    print(f"Wallet Public Key: {keypair.pubkey()}")

    wallet = Wallet(keypair)
    provider = Provider(connection, wallet)
    print("Created provider")

    drift_client = DriftClient(connection, wallet=wallet)
    await drift_client.subscribe()
    print("DriftClient initialized and subscribed")

    user_map = UserMap(UserMapConfig(drift_client, PollingConfig(frequency=10)))
    await user_map.subscribe()
    print("UserMap initialized and subscribed")

    config = SwiftOrderSubscriberConfig(
        drift_client=drift_client,
        user_map=user_map,
        drift_env="mainnet-beta",
        market_indexes=[0],
        keypair=keypair,
    )
    print("Created SignedMsgOrderSubscriberConfig")

    subscriber = SwiftOrderSubscriber(config)

    handler = partial(
        handle_and_fill_order, drift_client=drift_client, user_map=user_map
    )

    try:
        print("Starting subscriber...")
        await subscriber.subscribe(
            lambda order, decoded_msg: handler(order, decoded_msg)
        )
    except KeyboardInterrupt:
        print("KeyboardInterrupt received, shutting down...")
    except Exception as e:
        print(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        print("Unsubscribing and closing connections...")
        if subscriber and subscriber.subscribed:
            await subscriber.unsubscribe()
        if user_map and user_map.subscribed:
            await user_map.unsubscribe()
        if drift_client and drift_client.subscribed:
            await drift_client.unsubscribe()
        print("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
