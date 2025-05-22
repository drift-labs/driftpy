import asyncio
import os
import pprint

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair

from driftpy.constants.numeric_constants import BASE_PRECISION
from driftpy.drift_client import DriftClient
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
    is_variant,
)


async def take_and_make(
    direction: PositionDirection,
    market_index: int,
    maker_keypair: Keypair,
    taker_keypair: Keypair,
    connection: AsyncClient,
):
    print(f"Maker Pubkey: {maker_keypair.pubkey()}")
    print(f"Taker Pubkey: {taker_keypair.pubkey()}")

    maker_client = DriftClient(
        connection,
        wallet=maker_keypair,
        env="mainnet",
    )
    taker_client = DriftClient(connection, wallet=taker_keypair, env="mainnet")

    print("Subscribing Maker Client...")
    await maker_client.subscribe()
    print("Subscribing Taker Client...")
    await taker_client.subscribe()
    print("Clients Subscribed.")

    oracle_price_data = maker_client.get_oracle_price_data_for_perp_market(market_index)
    low_price = int(oracle_price_data.price * BASE_PRECISION // 1e6)
    high_price = int(low_price * 101 // 100)

    perp_market = maker_client.get_perp_market_account(market_index)
    base_asset_amount = perp_market.amm.min_order_size * 2

    print("Taker preparing order...")
    taker_base_asset_amount = base_asset_amount

    start_price = low_price if is_variant(direction, "Long") else high_price
    end_price = high_price if is_variant(direction, "Long") else low_price

    taker_order_params = OrderParams(
        market_index=market_index,
        order_type=OrderType.Market(),
        market_type=MarketType.Perp(),
        direction=direction,
        base_asset_amount=taker_base_asset_amount,
        auction_start_price=start_price,
        auction_end_price=end_price,
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
    maker_direction = (
        PositionDirection.Long()
        if is_variant(direction, "Short")
        else PositionDirection.Short()
    )

    maker_order_params = OrderParams(
        market_index=market_index,
        order_type=OrderType.Limit(),
        market_type=MarketType.Perp(),
        direction=maker_direction,
        base_asset_amount=maker_base_asset_amount,
        price=start_price,
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
    pprint.pprint(taker_info)

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


async def delta_neutral_take_and_make(
    market_index: int,
    maker_keypair: Keypair,
    taker_keypair: Keypair,
    connection: AsyncClient,
):
    await take_and_make(
        PositionDirection.Long(),
        market_index,
        maker_keypair,
        taker_keypair,
        connection,
    )
    await take_and_make(
        PositionDirection.Short(),
        market_index,
        maker_keypair,
        taker_keypair,
        connection,
    )


if __name__ == "__main__":
    market_index = 51
    maker_keypair = Keypair.from_base58_string(os.getenv("PRIVATE_KEY"))
    taker_keypair = Keypair.from_base58_string(os.getenv("PRIVATE_KEY_2"))
    connection = AsyncClient(os.getenv("RPC_TRITON"), commitment=Confirmed)
    asyncio.run(
        delta_neutral_take_and_make(
            market_index,
            maker_keypair,
            taker_keypair,
            connection,
        )
    )
