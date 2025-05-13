import asyncio
import os

from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts

from driftpy.constants.numeric_constants import BASE_PRECISION
from driftpy.drift_client import DriftClient
from driftpy.keypair import load_keypair
from driftpy.swift.util import generate_signed_msg_uuid
from driftpy.types import (
    MarketType,
    OrderParams,
    OrderParamsBitFlag,
    OrderTriggerCondition,
    OrderType,
    PositionDirection,
    PostOnlyParams,
    SignedMsgOrderParamsMessage,
)


async def main():
    load_dotenv()
    RPC_URL = os.getenv("RPC_TRITON")
    if not RPC_URL:
        raise ValueError("Set RPC_TRITON in .env")

    MAKER_PRIVATE_KEY = os.getenv("PRIVATE_KEY")
    TAKER_PRIVATE_KEY = os.getenv("PRIVATE_KEY_2")

    if not MAKER_PRIVATE_KEY or not TAKER_PRIVATE_KEY:
        raise ValueError(
            "Set PRIVATE_KEY and PRIVATE_KEY_2 in .env. PRIVATE_KEY_2 needs SOL and USDC."
        )
    if MAKER_PRIVATE_KEY == TAKER_PRIVATE_KEY:
        raise ValueError("PRIVATE_KEY and PRIVATE_KEY_2 must be different")

    connection = AsyncClient(RPC_URL, commitment=Confirmed)

    maker_keypair = load_keypair(MAKER_PRIVATE_KEY)
    taker_keypair = load_keypair(TAKER_PRIVATE_KEY)

    print(f"Maker Pubkey: {maker_keypair.pubkey()}")
    print(f"Taker Pubkey: {taker_keypair.pubkey()}")

    maker_client = DriftClient(
        connection,
        wallet=maker_keypair,
        env="mainnet",
    )
    taker_client = DriftClient(
        connection,
        wallet=taker_keypair,
        env="mainnet",
        opts=TxOpts(skip_preflight=True),
    )

    print("Subscribing Maker Client...")
    await maker_client.subscribe()
    print("Subscribing Taker Client...")
    await taker_client.subscribe()

    print("Clients Subscribed.")

    market_index = 0
    oracle_price_data = maker_client.get_oracle_price_data_for_perp_market(market_index)
    low_price = oracle_price_data.price
    high_price = oracle_price_data.price * 101 // 100

    print("Taker preparing order...")
    taker_base_asset_amount = int(0.2 * BASE_PRECISION)

    direction = PositionDirection.Long()

    taker_order_params = OrderParams(
        market_index=market_index,
        order_type=OrderType.Market(),
        market_type=MarketType.Perp(),
        direction=direction,
        base_asset_amount=taker_base_asset_amount,
        auction_start_price=low_price,
        auction_end_price=high_price,
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
    print(f"Taker slot: {taker_slot}")
    taker_uuid = generate_signed_msg_uuid()

    print(f"Taker order params: {taker_order_params}")
    taker_order_message = SignedMsgOrderParamsMessage(
        signed_msg_order_params=taker_order_params,
        sub_account_id=taker_client.active_sub_account_id,
        slot=taker_slot,
        uuid=taker_uuid,
        take_profit_order_params=None,
        stop_loss_order_params=None,
    )

    print(f"Taker order message: {taker_order_message}")

    signed_taker_order = taker_client.sign_signed_msg_order_params_message(
        taker_order_message
    )
    print(f"Taker signed order with UUID: {taker_uuid}")

    print("Maker preparing fill...")
    maker_base_asset_amount = taker_base_asset_amount
    maker_order_price = high_price

    maker_order_params = OrderParams(
        market_index=market_index,
        order_type=OrderType.Limit(),
        market_type=MarketType.Perp(),
        direction=PositionDirection.Short(),
        base_asset_amount=maker_base_asset_amount,
        price=maker_order_price,
        user_order_id=1,
        post_only=PostOnlyParams.MustPostOnly(),
        reduce_only=False,
        trigger_price=0,
        trigger_condition=OrderTriggerCondition.Above(),
        auction_start_price=0,
        auction_end_price=0,
        auction_duration=0,
        max_ts=None,
        oracle_price_offset=None,
        bit_flags=OrderParamsBitFlag.IMMEDIATE_OR_CANCEL,
    )

    taker_user_account_pubkey = taker_client.get_user_account_public_key()
    taker_user_account = taker_client.get_user_account()
    taker_stats_account_pubkey = taker_client.get_user_stats_public_key()

    taker_info = {
        "taker": taker_user_account_pubkey,
        "taker_user_account": taker_user_account,
        "taker_stats": taker_stats_account_pubkey,
        "signing_authority": taker_keypair.pubkey(),
    }

    print("Maker constructing place_and_make transaction...")
    ixs = []
    ixs.extend(
        await maker_client.get_place_and_make_signed_msg_perp_order_ixs(
            signed_msg_order_params=signed_taker_order,
            signed_msg_order_uuid=taker_uuid,
            taker_info=taker_info,
            order_params=maker_order_params,
            override_ix_count=3,
        )
    )

    print(f"Sending transaction with {len(ixs)} instructions...")
    try:
        tx_sig = await maker_client.send_ixs(ixs)
        print(f"Transaction sent: {tx_sig}")

        await asyncio.sleep(5)
        maker_user = maker_client.get_user()
        taker_user = taker_client.get_user()

        await maker_user.subscribe()
        await taker_user.subscribe()

    except Exception as e:
        print(f"Error sending transaction: {e}")
        if hasattr(e, "logs"):
            print("Transaction Logs:")
            for log in e.logs:
                print(log)

    finally:
        print("Unsubscribing clients...")
        await maker_client.unsubscribe()
        await taker_client.unsubscribe()
        print("Finished.")


if __name__ == "__main__":
    asyncio.run(main())
