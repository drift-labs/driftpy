from typing import Optional
from driftpy.accounts.types import DataAndSlot, WebsocketProgramAccountOptions
from driftpy.accounts.ws.multi_account_subscriber import WebSocketProgramAccountSubscriber
from driftpy.auction_subscriber.types import AuctionSubscriberConfig
from events import Events as EventEmitter
from solana.rpc.types import TxOpts
from driftpy.memcmp import get_user_filter, get_user_with_auction_filter
from driftpy.decode.user import decode_user
from solders.pubkey import Pubkey
from driftpy.types import UserAccount

class AuctionSubscriber:
    def __init__(self, config: AuctionSubscriberConfig):
        self.drift_client = config.drift_client
        self.opts: TxOpts = self.opts if self.opts is not None else self.drift_client.opts
        self.event_emitter = EventEmitter(("on_account_update"))
        self.resub_timeout_ms = config.resub_timeout_ms
        self.subscriber: Optional[WebSocketProgramAccountSubscriber] = None
        self.event_emitter.on("on_account_update")

    async def subscribe(self):
        if self.subscriber is None:
            filters = (get_user_filter(), get_user_with_auction_filter())
            options = WebsocketProgramAccountOptions(filters, self.opts.preflight_commitment, "base64")
            self.subscriber = WebSocketProgramAccountSubscriber(
                'AuctionSubscriber',
                'User',
                self.drift_client.program, 
                options, 
                self.on_update, 
                decode_user,
                self.resub_timeout_ms
                )

        await self.subscriber.subscribe()

    def on_update(self, account_id: Pubkey, data: DataAndSlot[UserAccount]):
        self.event_emitter.emit("on_account_update", data.data, account_id, data.slot)

    def unsubscribe(self):
        if self.subscriber is None:
            return
        self.subscriber.unsubscribe()
