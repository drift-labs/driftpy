from typing import Callable, Optional, TypeVar

from solana.rpc.commitment import Commitment

from driftpy.accounts.types import MarketUpdateCallback, WebsocketProgramAccountOptions
from driftpy.accounts.ws.program_account_subscriber import (
    WebSocketProgramAccountSubscriber,
)
from driftpy.memcmp import get_market_type_filter
from driftpy.types import market_type_to_string

T = TypeVar("T")


class WebsocketSubscription:
    def __init__(
        self,
        market_map,
        commitment: Commitment,
        on_update: MarketUpdateCallback,
        resub_timeout_ms: Optional[int] = None,
        decode: Optional[Callable[[bytes], T]] = None,
    ):
        self.market_map = market_map
        self.commitment = commitment
        self.on_update = on_update
        self.resub_timeout_ms = resub_timeout_ms
        self.subscriber = None
        self.decode = decode

    async def subscribe(self):
        if not self.subscriber:
            filters = (get_market_type_filter(self.market_map.market_type),)
            options = WebsocketProgramAccountOptions(filters, self.commitment, "base64")
            self.subscriber = WebSocketProgramAccountSubscriber(
                f"{market_type_to_string(self.market_map.market_type)}MarketMap",
                self.market_map.program,
                options,
                self.on_update,
                self.decode,
            )

        await self.subscriber.subscribe()

    async def unsubscribe(self):
        if not self.subscriber:
            return
        await self.subscriber.unsubscribe()
        self.subscriber = None
