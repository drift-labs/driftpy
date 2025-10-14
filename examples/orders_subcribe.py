import asyncio
import os
from typing import Optional

from anchorpy import Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment, Confirmed
from solders.pubkey import Pubkey

from driftpy.drift_client import DriftClient
from driftpy.events.event_subscriber import EventSubscriber
from driftpy.events.types import (
    EventSubscriptionOptions,
    EventType,
    GrpcLogProviderConfig,
    LogProviderConfig,
    WebsocketLogProviderConfig,
    WrappedEvent,
)

load_dotenv()

LOG_PROVIDER_TYPE = "websocket"  # use 'websocket' for websocket provider
GRPC_ENDPOINT = os.getenv("GRPC_ENDPOINT")
GRPC_AUTH_TOKEN = os.getenv("GRPC_AUTH_TOKEN")
HTTP_RPC_URL = os.getenv("RPC_TRITON")


class DriftSubscriber:
    def __init__(self, rpc_url: str):
        self.callbacks = []
        self.event_subscriber: Optional[EventSubscriber] = None
        self.connection = AsyncClient(rpc_url)
        self.drift_client = DriftClient(self.connection, Wallet.dummy(), env="mainnet")
        self.program = self.drift_client.program

    def add_callback(self, callback):
        self.callbacks.append(callback)
        if self.event_subscriber:
            self.event_subscriber.event_emitter.new_event += callback

    async def start(
        self,
        watched_address: Pubkey,
        event_types: tuple[EventType],
        commitment: Commitment,
    ):
        log_provider_conf: LogProviderConfig

        if LOG_PROVIDER_TYPE == "grpc":
            print("Using gRPC Log Provider")
            if not GRPC_ENDPOINT:
                raise ValueError(
                    "GRPC_ENDPOINT environment variable must be set for gRPC provider"
                )
            log_provider_conf = GrpcLogProviderConfig(
                endpoint=GRPC_ENDPOINT, token=GRPC_AUTH_TOKEN if GRPC_AUTH_TOKEN else ""
            )
        elif LOG_PROVIDER_TYPE == "websocket":
            print("Using WebSocket Log Provider")
            log_provider_conf = WebsocketLogProviderConfig()
        else:
            raise ValueError(
                f"Unsupported LOG_PROVIDER_TYPE: {LOG_PROVIDER_TYPE}. Choose 'websocket' or 'grpc'."
            )

        options = EventSubscriptionOptions(
            address=watched_address,
            event_types=event_types,
            max_tx=4096,
            max_events_per_type=4096,
            order_by="blockchain",
            order_dir="asc",
            commitment=commitment,
            log_provider_config=log_provider_conf,
        )

        self.event_subscriber = EventSubscriber(self.connection, self.program, options)
        self.event_subscriber.subscribe()
        print("Subscribed to EventSubscriber.")

        for callback in self.callbacks:
            self.event_subscriber.event_emitter.new_event += callback


def handle_rpc_event(event: WrappedEvent):
    print(f"Received Event: {event.event_type}, Slot: {event.slot}, Tx: {event.tx_sig}")
    # print(event) # Uncomment for full event details


async def main():
    if not HTTP_RPC_URL:
        raise ValueError("RPC_TRITON (HTTP/WS RPC URL) environment variable is not set")

    print(f"Using LOG_PROVIDER_TYPE: {LOG_PROVIDER_TYPE}")
    if LOG_PROVIDER_TYPE == "grpc":
        if not GRPC_ENDPOINT:
            print(
                "Warning: GRPC_ENDPOINT not set. gRPC provider will fail if selected."
            )
        print(f"gRPC Endpoint: {GRPC_ENDPOINT}")
        print(f"gRPC Token: {'Set' if GRPC_AUTH_TOKEN else 'Not Set'}")

    print(f"HTTP/WS RPC URL: {HTTP_RPC_URL}")

    watched_test_address = "Fe4hMZrg7R97ZrbSScWBXUpQwZB9gzBnhodTCGyjkHsG"
    event_subscriber_handler = DriftSubscriber(rpc_url=HTTP_RPC_URL)
    event_subscriber_handler.add_callback(handle_rpc_event)

    await event_subscriber_handler.start(
        watched_address=Pubkey.from_string(watched_test_address),
        event_types=(
            "OrderRecord",
            "OrderActionRecord",
        ),
        commitment=Confirmed,
    )

    print("Event subscriber started. Listening for events...")
    try:
        await asyncio.Future()  # Keep alive
    except asyncio.CancelledError:
        print("Main task cancelled.")
    finally:
        if (
            event_subscriber_handler.event_subscriber
            and event_subscriber_handler.event_subscriber.subscribed
        ):
            print("Unsubscribing...")
            await event_subscriber_handler.event_subscriber.unsubscribe()
            print("Unsubscribed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting due to KeyboardInterrupt...")
    except ValueError as e:
        print(f"Configuration Error: {e}")
