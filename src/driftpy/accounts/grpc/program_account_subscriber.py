import asyncio
import time
from typing import Callable, Dict, Optional, TypeVar

import base58
import grpc.aio
from anchorpy.program.core import Program
from solana.rpc.commitment import Commitment
from solders.pubkey import Pubkey

from driftpy.accounts.grpc.account_subscriber import TritonAuthMetadataPlugin
from driftpy.accounts.grpc.geyser_codegen import geyser_pb2, geyser_pb2_grpc
from driftpy.accounts.types import (
    DataAndSlot,
    GrpcProgramAccountOptions,
    MarketUpdateCallback,
    UpdateCallback,
)
from driftpy.types import GrpcConfig

T = TypeVar("T")


class GrpcProgramAccountSubscriber:
    def __init__(
        self,
        subscription_name: str,
        program: Program,
        grpc_config: GrpcConfig,
        on_update: Optional[UpdateCallback | MarketUpdateCallback],
        options: GrpcProgramAccountOptions,
        decode: Optional[Callable[[bytes], T]] = None,
    ):
        self.subscription_name = subscription_name
        self.program = program
        self.grpc_config = grpc_config
        self.options = options
        self.task = None
        self.on_update = on_update
        self.decode = (
            decode if decode is not None else self.program.coder.accounts.decode
        )
        self.subscribed_accounts: Dict[Pubkey, DataAndSlot[T]] = {}
        self.stream = None
        self.receiving_data = False
        self.subscribed = False
        self.is_unsubscribing = False
        self.latest_slot = 0
        self.channel = self._create_grpc_channel(grpc_config)
        self.client = geyser_pb2_grpc.GeyserStub(self.channel)

    def _create_grpc_channel(self, config: GrpcConfig) -> grpc.aio.Channel:
        auth = TritonAuthMetadataPlugin(config.token)
        ssl_creds = grpc.ssl_channel_credentials()
        call_creds = grpc.metadata_call_credentials(auth)
        combined_creds = grpc.composite_channel_credentials(ssl_creds, call_creds)
        return grpc.aio.secure_channel(config.endpoint, credentials=combined_creds)

    async def _create_subscribe_request(self):
        request = geyser_pb2.SubscribeRequest()

        account_filter = geyser_pb2.SubscribeRequestFilterAccounts()
        request.accounts["program_monitor"].CopyFrom(account_filter)

        account_filter.owner.append(str(self.program.program_id))

        if self.options.filters:
            for memcmp_filter_opt in self.options.filters:
                memcmp_filter = geyser_pb2.SubscribeRequestFilterAccountsFilter()
                memcmp_filter.memcmp.offset = memcmp_filter_opt.offset
                memcmp_filter.memcmp.bytes = base58.b58decode(memcmp_filter_opt.bytes)
                account_filter.filters.append(memcmp_filter)

        account_filter.nonempty_txn_signature = True

        request.accounts["program_monitor"].CopyFrom(account_filter)
        request.commitment = geyser_pb2.CommitmentLevel.CONFIRMED
        if self.options.commitment == Commitment("finalized"):
            request.commitment = geyser_pb2.CommitmentLevel.FINALIZED
        elif self.options.commitment == Commitment("processed"):
            request.commitment = geyser_pb2.CommitmentLevel.PROCESSED

        yield request

        while True:
            await asyncio.sleep(30)
            ping_request = geyser_pb2.SubscribeRequest()
            ping_request.ping.id = int(time.time())
            yield ping_request

    async def subscribe(self):
        if self.subscribed:
            return
        self.task = asyncio.create_task(self._subscribe_grpc())
        return self.task

    async def _subscribe_grpc(self):
        while True:
            try:
                request_iterator = self._create_subscribe_request()
                self.stream = self.client.Subscribe(request_iterator)
                await self.stream.wait_for_connection()

                async for update in self.stream:
                    await self._process_update(update)

            except Exception as e:
                print(f"Error in grpc subscription {self.subscription_name}: {e}")
                if self.stream:
                    await self.stream.cancel()
                    self.stream = None
                await asyncio.sleep(5)
                if self.is_unsubscribing:
                    break

    async def _process_update(self, update):
        if update.HasField("ping") or update.HasField("pong"):
            return

        if not update.HasField("account"):
            return

        slot = int(update.account.slot)
        if slot < self.latest_slot:
            print(f"Received stale data from slot {slot}")
            return

        self.latest_slot = slot
        account_info = {
            "owner": Pubkey.from_bytes(update.account.account.owner),
            "data": bytes(update.account.account.data),
            "executable": update.account.account.executable,
        }

        if not account_info["data"]:
            return

        decoded_data = (
            self.decode(account_info["data"]) if self.decode else account_info
        )
        new_data = DataAndSlot(slot, decoded_data)
        pubkey = Pubkey.from_bytes(update.account.account.pubkey)

        if self.on_update is not None and callable(self.on_update):
            await self.on_update(str(pubkey), new_data)  # type: ignore

        self.receiving_data = True
        self._update_data(pubkey, new_data)

    def _update_data(self, account: Pubkey, new_data: Optional[DataAndSlot[T]]):
        if new_data is None:
            return
        self.subscribed_accounts[account] = new_data  # type: ignore

    async def unsubscribe(self):
        self.is_unsubscribing = True
        self.receiving_data = False
        if self.task:
            self.task.cancel()
            self.task = None
        if self.stream:
            self.stream.cancel()
            self.stream = None
        if self.channel:
            await self.channel.close()
        self.is_unsubscribing = False
        self.subscribed = False
