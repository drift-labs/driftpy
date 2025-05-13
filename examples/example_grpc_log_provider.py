import asyncio
import os

from dotenv import load_dotenv
from solana.rpc.commitment import Commitment

from driftpy.events.grpc_log_provider import GrpcLogProvider
from driftpy.events.types import GrpcLogProviderConfig

load_dotenv()


async def simple_log_callback(signature: str, slot: int, logs: list[str]):
    print(f"Received logs for tx: {signature} in slot: {slot}")
    print("---")


async def main():
    GRPC_ENDPOINT = os.getenv("GRPC_ENDPOINT")
    AUTH_TOKEN = os.getenv("GRPC_AUTH_TOKEN")
    if not GRPC_ENDPOINT or not AUTH_TOKEN:
        raise ValueError(
            "GRPC_ENDPOINT and GRPC_AUTH_TOKEN must be set in the environment"
        )

    USER_ACCOUNT_TO_FILTER = "BrRpSaQ6hFDw8darPCyP9Sw7sjydMFQqB4ECAotXSEci"
    print(f"Attempting to connect to gRPC endpoint: {GRPC_ENDPOINT}")

    grpc_provider_config = GrpcLogProviderConfig(
        endpoint=GRPC_ENDPOINT,
        token=AUTH_TOKEN,
    )

    commitment = Commitment("confirmed")

    log_provider = GrpcLogProvider(
        grpc_config=grpc_provider_config,
        commitment=commitment,
        user_account_to_filter=USER_ACCOUNT_TO_FILTER,
    )

    print("Subscribing to logs...")
    await log_provider.subscribe(simple_log_callback)

    run_duration = 60
    print(f"Listening for logs for {run_duration} seconds...")

    try:
        for i in range(run_duration):
            if not log_provider.is_subscribed():
                print("Subscription lost unexpectedly.")
                break
            await asyncio.sleep(1)
            if i % 10 == 0 and i > 0:
                print(f"Still subscribed after {i} seconds...")

    except asyncio.CancelledError:
        print("Run cancelled.")
    finally:
        print("Unsubscribing...")
        await log_provider.unsubscribe()
        print("Example finished.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting due to KeyboardInterrupt...")
