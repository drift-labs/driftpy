import asyncio

from events import Events as EventEmitter
from solders.pubkey import Pubkey

from driftpy.accounts.grpc.account_subscriber import GrpcAccountSubscriber
from driftpy.accounts.types import DataAndSlot
from driftpy.auction_subscriber.types import GrpcAuctionSubscriberConfig
from driftpy.decode.user import decode_user
from driftpy.types import UserAccount


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
        self.event_emitter = EventEmitter(("on_account_update"))
        self.event_emitter.on("on_account_update")

    async def on_update(self, account_pubkey: str, data: DataAndSlot[UserAccount]):
        self.event_emitter.on_account_update(
            data.data, Pubkey.from_string(account_pubkey), data.slot
        )

    async def subscribe(self):
        if self.subscribers:
            return

        accounts = await self.drift_client.program.account["User"].all()
        auction_accounts = [acc for acc in accounts if acc.account.in_auction()]
        for account in auction_accounts:
            subscriber = GrpcAccountSubscriber(
                self.config.grpc_config,
                "AuctionSubscriber",
                self.drift_client.program,
                account.public_key,
                self.commitment,
                decode_user,
            )
            await subscriber.subscribe()
            self.subscribers.append(subscriber)

    def unsubscribe(self):
        if not self.subscribers:
            return

        for subscriber in self.subscribers:
            asyncio.create_task(subscriber.unsubscribe())
        self.subscribers.clear()
