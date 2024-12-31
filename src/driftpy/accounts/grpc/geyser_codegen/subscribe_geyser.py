import logging
import os
import time
from typing import Iterator, Optional

import geyser_pb2
import geyser_pb2_grpc
import grpc


def _triton_sign_request(
    callback: grpc.AuthMetadataPluginCallback,
    x_token: Optional[str],
    error: Optional[Exception],
):
    metadata = (("x-token", x_token),)
    return callback(metadata, error)


class TritonAuthMetadataPlugin(grpc.AuthMetadataPlugin):
    def __init__(self, x_token: str):
        self.x_token = x_token

    def __call__(
        self,
        context: grpc.AuthMetadataContext,
        callback: grpc.AuthMetadataPluginCallback,
    ):
        return _triton_sign_request(callback, self.x_token, None)


def create_subscribe_request() -> Iterator[geyser_pb2.SubscribeRequest]:
    request = geyser_pb2.SubscribeRequest()

    # Create the account filter
    account_filter = geyser_pb2.SubscribeRequestFilterAccounts()

    # Add a specific account to monitor
    # Note: This needs to be the base58 encoded public key
    account_filter.account.append("dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH")
    account_filter.account.append("DRiP8pChV3hr8FkdgPpxpVwQh3dHnTzHgdbn5Z3fmwHc")
    account_filter.account.append("Fe4hMZrg7R97ZrbSScWBXUpQwZB9gzBnhodTCGyjkHsG")
    account_filter.nonempty_txn_signature = True

    # Copy the filter into the request
    request.accounts["account_monitor"].CopyFrom(account_filter)
    request.commitment = geyser_pb2.CommitmentLevel.CONFIRMED

    yield request

    # Keep connection alive with pings
    while True:
        time.sleep(30)
        ping_request = geyser_pb2.SubscribeRequest()
        ping_request.ping.id = int(time.time())
        yield ping_request


def handle_subscribe_updates(stub: geyser_pb2_grpc.GeyserStub):
    """
    Handles the streaming updates from the subscription.
    Each update can contain different types of data based on our filters.
    """
    try:
        request_iterator = create_subscribe_request()
        print("Starting subscription stream...")

        response_stream = stub.Subscribe(request_iterator)

        for update in response_stream:
            if update.HasField("account"):
                print("\nAccount Update:")
                print(f"  Pubkey: {update.account.account.pubkey.hex()}")
                print(f"  Owner: {update.account.account.owner.hex()}")
                print(f"  Lamports: {update.account.account.lamports}")
                print(f"  Slot: {update.account.slot}")
                if update.account.account.txn_signature:
                    print(
                        f"  Transaction: {update.account.account.txn_signature.hex()}"
                    )

            elif update.HasField("pong"):
                print(f"Received pong: {update.pong.id}")

    except grpc.RpcError as e:
        logging.error(f"RPC error occurred: {str(e)}")
        raise


def run_subscription_client():
    rpc_fqdn = os.environ.get("RPC_FDQN")
    x_token = os.environ.get("X_TOKEN")

    auth = TritonAuthMetadataPlugin(x_token)
    ssl_creds = grpc.ssl_channel_credentials()
    call_creds = grpc.metadata_call_credentials(auth)
    combined_creds = grpc.composite_channel_credentials(ssl_creds, call_creds)

    with grpc.secure_channel(rpc_fqdn, credentials=combined_creds) as channel:
        stub = geyser_pb2_grpc.GeyserStub(channel)
        handle_subscribe_updates(stub)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_subscription_client()
