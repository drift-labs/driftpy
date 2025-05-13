import asyncio
import time
from typing import Optional

import base58
import grpc.aio
from solana.rpc.commitment import Commitment
from solders.pubkey import Pubkey

from driftpy.accounts.grpc.account_subscriber import TritonAuthMetadataPlugin
from driftpy.accounts.grpc.geyser_codegen import geyser_pb2, geyser_pb2_grpc
from driftpy.constants.config import DRIFT_PROGRAM_ID
from driftpy.types import GrpcLogProviderConfig, LogProviderCallback


class GrpcLogProvider:
    def __init__(
        self,
        grpc_config: GrpcLogProviderConfig,
        commitment: Commitment,
        user_account_to_filter: Optional[Pubkey] = None,
        program_id: Pubkey = DRIFT_PROGRAM_ID,
    ):
        self.grpc_config = grpc_config
        self.program_id = program_id
        self.commitment = commitment
        self.user_account_to_filter = user_account_to_filter
        self.task = None
        self.client: Optional[geyser_pb2_grpc.GeyserStub] = None
        self.channel: Optional[grpc.aio.Channel] = None
        self.stream: Optional[grpc.aio.StreamStreamClient] = None
        self.is_unsubscribing = False
        self.subscribed = False
        self.callback: Optional[LogProviderCallback] = None
        self.latest_slot = 0

    def _create_grpc_channel(self, config: GrpcLogProviderConfig) -> grpc.aio.Channel:
        auth = TritonAuthMetadataPlugin(config.token)
        ssl_creds = grpc.ssl_channel_credentials()
        call_creds = grpc.metadata_call_credentials(auth)
        combined_creds = grpc.composite_channel_credentials(ssl_creds, call_creds)
        return grpc.aio.secure_channel(config.endpoint, credentials=combined_creds)

    async def _create_subscribe_request(self):
        request = geyser_pb2.SubscribeRequest()

        transaction_filter = geyser_pb2.SubscribeRequestFilterTransactions()
        transaction_filter.vote = False
        transaction_filter.failed = False

        # Use account_required for an AND condition
        transaction_filter.account_required.append(str(self.program_id))

        if self.user_account_to_filter:
            print(
                f"Adding user account to filter (required): {self.user_account_to_filter}"
            )
            transaction_filter.account_required.append(str(self.user_account_to_filter))

        request.transactions["drift_program_logs"].CopyFrom(transaction_filter)

        if self.commitment == Commitment("finalized"):
            request.commitment = geyser_pb2.CommitmentLevel.FINALIZED
        elif self.commitment == Commitment("processed"):
            request.commitment = geyser_pb2.CommitmentLevel.PROCESSED
        else:  # confirmed or default
            request.commitment = geyser_pb2.CommitmentLevel.CONFIRMED

        yield request

        while True:
            await asyncio.sleep(30)  # Send a ping every 30 seconds
            ping_request = geyser_pb2.SubscribeRequest()
            ping_request.ping.id = int(time.time())
            yield ping_request

    async def subscribe(self, callback: LogProviderCallback):
        if self.subscribed:
            return

        self.callback = callback
        self.channel = self._create_grpc_channel(self.grpc_config)
        self.client = geyser_pb2_grpc.GeyserStub(self.channel)
        self.task = asyncio.create_task(self._subscribe_grpc())
        self.subscribed = True
        return self.task

    async def _subscribe_grpc(self):
        while not self.is_unsubscribing:
            try:
                request_iterator = self._create_subscribe_request()
                print("[GrpcLogProvider] Creating gRPC stream...")
                self.stream = self.client.Subscribe(request_iterator)
                print("[GrpcLogProvider] Stream created. Waiting for connection...")
                await self.stream.wait_for_connection()
                print("[GrpcLogProvider] Stream connected.")

                async for update in self.stream:
                    await self._process_update(update)

            except Exception as e:
                print(f"Error in gRPC log subscription: {e}")
                if self.stream:
                    await self.stream.cancel()
                    self.stream = None
                if not self.is_unsubscribing:
                    await asyncio.sleep(5)  # Wait before retrying
                else:
                    break  # Exit loop if unsubscribe was called

    async def _process_update(self, update: geyser_pb2.SubscribeUpdate):
        if update.HasField("ping") or update.HasField("pong"):
            return

        if not update.HasField("transaction"):
            print("[GrpcLogProvider] Update does not have transaction field.")
            return

        slot = int(update.transaction.slot)
        if slot < self.latest_slot:
            # can happen if a slot has multiple transactions and one is processed after a later slot's txn
            # print(f"Received stale log data from slot {slot}, latest was {self.latest_slot}")
            pass  # do not return, process anyway

        self.latest_slot = max(self.latest_slot, slot)

        if (
            update.transaction.transaction is None
            or update.transaction.transaction.meta is None
            or update.transaction.transaction.transaction is None
        ):
            return

        logs = list(update.transaction.transaction.meta.log_messages)
        signature_bytes = update.transaction.transaction.transaction.signatures[0]
        signature = base58.b58encode(signature_bytes).decode("utf-8")

        if (
            update.transaction.transaction.meta.err
            and str(update.transaction.transaction.meta.err).strip()
        ):
            print(
                f"[GrpcLogProvider] Transaction {signature} at slot {slot} genuinely failed. Error: {str(update.transaction.transaction.meta.err).strip()}"
            )
            return

        if self.callback:
            await self.callback(signature, slot, logs)

    def is_subscribed(self) -> bool:
        return self.subscribed and self.task is not None and not self.task.done()

    async def unsubscribe(self):
        if not self.subscribed and not self.is_unsubscribing:
            return

        self.is_unsubscribing = True
        self.subscribed = False

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass  # Expected
            self.task = None

        if self.stream:
            self.stream.cancel()
            self.stream = None

        if self.channel:
            await self.channel.close()
            self.channel = None

        self.client = None
        self.callback = None
        self.is_unsubscribing = False
        print("gRPC log provider unsubscribed.")
