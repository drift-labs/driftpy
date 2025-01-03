import asyncio
import os

from anchorpy.provider import Provider, Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.auction_subscriber.grpc_auction_subscriber import GrpcAuctionSubscriber

# Auction subscriber imports
from driftpy.auction_subscriber.types import GrpcAuctionSubscriberConfig

# Drift imports
from driftpy.drift_client import DriftClient
from driftpy.types import GrpcConfig, UserAccount

load_dotenv()


# Example callback
def on_auction_account_update(user_account: UserAccount, pubkey, slot: int):
    """
    This function is called whenever an auctioned User account is updated.
    """
    print(
        f"[AUCTION UPDATE] Slot={slot} PublicKey={pubkey}, UserAccount={user_account}"
    )


async def main():
    """
    Main entrypoint: create a gRPC-based Drift client, set up the GrpcAuctionSubscriber,
    and attach a callback that prints changes to auction accounts.
    """

    # 1) Load environment variables
    rpc_fqdn = os.environ.get("RPC_FQDN")  # e.g. "grpcs://my-geyser-endpoint.com:443"
    x_token = os.environ.get("X_TOKEN")  # your auth token
    private_key = os.environ.get("PRIVATE_KEY")  # base58-encoded, e.g. "42Ab..."
    rpc_url = os.environ.get("RPC_TRITON")  # normal Solana JSON-RPC for sending tx

    if not (rpc_fqdn and x_token and private_key and rpc_url):
        raise ValueError("RPC_FQDN, X_TOKEN, PRIVATE_KEY, and RPC_TRITON must be set")

    wallet = Wallet(Keypair.from_base58_string(private_key))
    connection = AsyncClient(rpc_url)
    provider = Provider(connection, wallet)

    drift_client = DriftClient(
        provider.connection,
        provider.wallet,
        "mainnet",
        account_subscription=AccountSubscriptionConfig(
            "grpc",
            grpc_config=GrpcConfig(
                endpoint=rpc_fqdn,
                token=x_token,
            ),
        ),
    )

    await drift_client.subscribe()

    auction_subscriber_config = GrpcAuctionSubscriberConfig(
        drift_client=drift_client,
        grpc_config=GrpcConfig(endpoint=rpc_fqdn, token=x_token),
        commitment=provider.connection.commitment,  # or "confirmed"
    )
    auction_subscriber = GrpcAuctionSubscriber(auction_subscriber_config)

    auction_subscriber.event_emitter.on_account_update += on_auction_account_update
    await auction_subscriber.subscribe()
    print("AuctionSubscriber is now watching for changes to in-auction User accounts.")

    try:
        while True:
            await asyncio.sleep(10)
    except KeyboardInterrupt:
        print("Unsubscribing from auction accounts...")
        auction_subscriber.unsubscribe()


if __name__ == "__main__":
    asyncio.run(main())
    print("Done.")
