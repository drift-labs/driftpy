import asyncio
import time
from typing import Callable, Optional, TypeVar

import grpc.aio
from anchorpy.program.core import Program
from solana.rpc.commitment import Commitment
from solders.pubkey import Pubkey

from driftpy.accounts.grpc.geyser_codegen import geyser_pb2, geyser_pb2_grpc
from driftpy.accounts.types import DataAndSlot
from driftpy.accounts.ws.account_subscriber import WebsocketAccountSubscriber
from driftpy.types import GrpcConfig

T = TypeVar("T")


class TritonAuthMetadataPlugin(grpc.AuthMetadataPlugin):
    def __init__(self, x_token: str):
        self.x_token = x_token

    def __call__(
        self,
        context: grpc.AuthMetadataContext,
        callback: grpc.AuthMetadataPluginCallback,
    ):
        metadata = (("x-token", self.x_token),)
        callback(metadata, None)


class GrpcAccountSubscriber(WebsocketAccountSubscriber[T]):
    def __init__(
        self,
        grpc_config: GrpcConfig,
        account_name: str,
        program: Program,
        account_public_key: Pubkey,
        commitment: Commitment = Commitment("confirmed"),
        decode: Optional[Callable[[bytes], T]] = None,
        initial_data: Optional[DataAndSlot[T]] = None,
    ):
        super().__init__(account_public_key, program, commitment, decode, initial_data)
        self.client = self._create_grpc_client(grpc_config)
        self.stream = None
        self.listener_id = None
        self.account_name = account_name
        self.decode = (
            decode if decode is not None else self.program.coder.accounts.decode
        )

    def _create_grpc_client(self, config: GrpcConfig) -> geyser_pb2_grpc.GeyserStub:
        auth = TritonAuthMetadataPlugin(config.token)
        ssl_creds = grpc.ssl_channel_credentials()
        call_creds = grpc.metadata_call_credentials(auth)
        combined_creds = grpc.composite_channel_credentials(ssl_creds, call_creds)

        channel = grpc.aio.secure_channel(config.endpoint, credentials=combined_creds)
        return geyser_pb2_grpc.GeyserStub(channel)

    async def subscribe(self) -> Optional[asyncio.Task[None]]:
        if self.listener_id is not None:
            return

        self.task = asyncio.create_task(self._subscribe_grpc())
        return self.task

    async def _subscribe_grpc(self):
        """Internal method to handle the gRPC subscription"""
        if self.data_and_slot is None:
            await self.fetch()

        try:
            request_iterator = self._create_subscribe_request()
            self.stream = self.client.Subscribe(request_iterator)
            await self.stream.wait_for_connection()

            self.listener_id = 1

            async for update in self.stream:
                try:
                    if update.HasField("ping") or update.HasField("pong"):
                        continue

                    if not update.HasField("account"):
                        print(f"No account for {self.account_name}")
                        continue

                    slot = int(update.account.slot)
                    account_info = {
                        "owner": Pubkey.from_bytes(update.account.account.owner),
                        "lamports": int(update.account.account.lamports),
                        "data": bytes(update.account.account.data),
                        "executable": update.account.account.executable,
                        "rent_epoch": int(update.account.account.rent_epoch),
                    }

                    if not account_info["data"]:
                        print(f"No data for {self.account_name}")
                        continue

                    decoded_data = (
                        self.decode(account_info["data"])
                        if self.decode
                        else account_info
                    )
                    self.update_data(DataAndSlot(slot, decoded_data))

                except Exception as e:
                    print(f"Error processing account data for {self.account_name}: {e}")
                    break

        except Exception as e:
            print(f"Error in gRPC subscription for {self.account_name}: {e}")
            if self.stream:
                self.stream.cancel()
            self.listener_id = None
            raise e

    async def _create_subscribe_request(self):
        request = geyser_pb2.SubscribeRequest()
        account_filter = geyser_pb2.SubscribeRequestFilterAccounts()
        account_filter.account.append(str(self.pubkey))
        account_filter.nonempty_txn_signature = True
        request.accounts["account_monitor"].CopyFrom(account_filter)

        request.commitment = geyser_pb2.CommitmentLevel.CONFIRMED
        if self.commitment == Commitment("finalized"):
            request.commitment = geyser_pb2.CommitmentLevel.FINALIZED
        if self.commitment == Commitment("processed"):
            request.commitment = geyser_pb2.CommitmentLevel.PROCESSED

        yield request

        while True:
            await asyncio.sleep(30)
            ping_request = geyser_pb2.SubscribeRequest()
            ping_request.ping.id = int(time.time())
            yield ping_request

    async def unsubscribe(self) -> None:
        if self.listener_id is not None:
            try:
                if self.stream:
                    self.stream.cancel()
                self.listener_id = None
            except Exception as e:
                print(f"Error unsubscribing from account {self.account_name}: {e}")
                raise e

    def update_data(self, new_data: Optional[DataAndSlot[T]]):
        if new_data is None:
            return

        if self.data_and_slot is None or new_data.slot >= self.data_and_slot.slot:
            self.data_and_slot = new_data
