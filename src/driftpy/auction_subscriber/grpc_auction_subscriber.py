import asyncio

from events.events import Events, _EventSlot
from solders.pubkey import Pubkey

from driftpy.accounts.grpc.account_subscriber import GrpcAccountSubscriber
from driftpy.accounts.grpc.program_account_subscriber import (
    GrpcProgramAccountSubscriber,
)
from driftpy.accounts.types import DataAndSlot, GrpcProgramAccountOptions
from driftpy.auction_subscriber.types import GrpcAuctionSubscriberConfig
from driftpy.decode.user import decode_user
from driftpy.memcmp import get_user_filter, get_user_with_auction_filter
from driftpy.types import UserAccount


class GrpcAuctionEvents(Events):
    __events__ = ("on_account_update",)
    on_account_update: _EventSlot


class GrpcAuctionSubscriber:
    def __init__(self, config: GrpcAuctionSubscriberConfig):
        self.config = config
        self.drift_client = config.drift_client
        self.commitment = (
            config.commitment
            if config.commitment is not None
            else self.drift_client.connection.commitment
        )
        self.subscribers: list[GrpcAccountSubscriber] = []
        self.event_emitter = GrpcAuctionEvents()

    async def on_update(self, account_pubkey: str, data: DataAndSlot[UserAccount]):
        self.event_emitter.on_account_update(
            data.data, Pubkey.from_string(account_pubkey), data.slot
        )

    async def subscribe(self):
        if self.subscribers:
            return

        filters = (get_user_filter(), get_user_with_auction_filter())
        options = GrpcProgramAccountOptions(filters, self.commitment)
        self.subscriber = GrpcProgramAccountSubscriber(
            grpc_config=self.config.grpc_config,
            subscription_name="AuctionSubscriber",
            program=self.drift_client.program,
            options=options,
            on_update=self.on_update,
            decode=decode_user,
        )
        await self.subscriber.subscribe()

    def unsubscribe(self):
        if not self.subscribers:
            return

        for subscriber in self.subscribers:
            asyncio.create_task(subscriber.unsubscribe())
        self.subscribers.clear()
