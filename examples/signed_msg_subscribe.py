import asyncio
import os

from anchorpy.provider import Provider, Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment

from driftpy.drift_client import DriftClient
from driftpy.keypair import load_keypair
from driftpy.swift.order_subscriber import (
    SwiftOrderSubscriber,
    SwiftOrderSubscriberConfig,
)
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import PollingConfig, UserMapConfig


async def handle_order(order, signed_msg_order_params_message):
    print()
    print("==>")
    print(f"Received order: {order}")
    print(f"SignedMsgOrderParamsMessage: {signed_msg_order_params_message}")
    print()


async def main():
    print("Starting main function")
    load_dotenv()
    keypair = load_keypair(os.getenv("PRIVATE_KEY"))
    connection = AsyncClient(
        os.getenv("RPC_TRITON"), commitment=Commitment("confirmed")
    )
    print("Created Solana connection")

    provider = Provider(connection, Wallet.dummy())
    provider.connection = connection
    print("Created provider")

    drift_client = DriftClient(connection, wallet=Wallet.dummy())
    await drift_client.subscribe()
    print("DriftClient initialized and subscribed")

    user_map = UserMap(UserMapConfig(drift_client, PollingConfig(frequency=2)))
    await user_map.subscribe()
    print("UserMap initialized and subscribed")

    config = SwiftOrderSubscriberConfig(
        drift_client=drift_client,
        user_map=user_map,
        drift_env="mainnet-beta",
        market_indexes=[0, 1, 2],
        keypair=keypair,
    )
    print("Created SignedMsgOrderSubscriberConfig")

    subscriber = SwiftOrderSubscriber(config)

    try:
        print("Starting subscriber")
        await subscriber.subscribe(handle_order)
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        if subscriber:
            await subscriber.unsubscribe()
        if user_map:
            await user_map.unsubscribe()
        if drift_client:
            await drift_client.unsubscribe()
        if connection:
            await connection.close()
            print("Connection closed")


if __name__ == "__main__":
    print("Starting main")
    asyncio.run(main())
