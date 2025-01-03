import asyncio
from typing import Optional

from events.events import Events, _EventSlot
from solders.pubkey import Pubkey

from driftpy.accounts.types import DataAndSlot, WebsocketProgramAccountOptions
from driftpy.accounts.ws.program_account_subscriber import (
    WebSocketProgramAccountSubscriber,
)
from driftpy.auction_subscriber.types import AuctionSubscriberConfig
from driftpy.decode.user import decode_user
from driftpy.memcmp import get_user_filter, get_user_with_auction_filter
from driftpy.types import UserAccount


class AuctionEvents(Events):
    """
    Subclass to explicitly declare the on_account_update event
    both in __events__ and as a typed attribute.
    """

    __events__ = ("on_account_update",)
    on_account_update: _EventSlot


class AuctionSubscriber:
    def __init__(self, config: AuctionSubscriberConfig):
        self.drift_client = config.drift_client
        self.commitment = (
            config.commitment
            if config.commitment is not None
            else self.drift_client.connection.commitment
        )
        self.resub_timeout_ms = config.resub_timeout_ms
        self.subscriber: Optional[WebSocketProgramAccountSubscriber] = None
        self.event_emitter = AuctionEvents()

    async def on_update(self, account_pubkey: str, data: DataAndSlot[UserAccount]):
        self.event_emitter.on_account_update(
            data.data,
            Pubkey.from_string(account_pubkey),
            data.slot,  # type: ignore
        )

    async def subscribe(self):
        if self.subscriber is None:
            filters = (get_user_filter(), get_user_with_auction_filter())
            options = WebsocketProgramAccountOptions(filters, self.commitment, "base64")
            self.subscriber = WebSocketProgramAccountSubscriber(
                "AuctionSubscriber",
                self.drift_client.program,
                options,
                self.on_update,
                decode_user,
                self.resub_timeout_ms,
            )

        if self.subscriber.subscribed:
            return

        await self.subscriber.subscribe()

    def unsubscribe(self):
        if self.subscriber is None:
            return
        asyncio.create_task(self.subscriber.unsubscribe())
