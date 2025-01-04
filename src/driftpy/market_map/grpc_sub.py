from typing import Callable, Optional, TypeVar

from solana.rpc.commitment import Commitment

from driftpy.accounts.grpc.program_account_subscriber import (
    GrpcProgramAccountSubscriber,
)
from driftpy.accounts.types import GrpcProgramAccountOptions, MarketUpdateCallback
from driftpy.market_map.market_map import MarketMap
from driftpy.memcmp import get_market_type_filter
from driftpy.types import GrpcConfig, market_type_to_string

T = TypeVar("T")


class GrpcSubscription:
    def __init__(
        self,
        grpc_config: GrpcConfig,
        market_map: MarketMap,
        commitment: Commitment,
        on_update: MarketUpdateCallback,
        decode: Optional[Callable[[bytes], T]] = None,
    ):
        self.grpc_config = grpc_config
        self.market_map = market_map
        self.commitment = commitment
        self.on_update = on_update
        self.subscriber = None
        self.decode = decode

    async def subscribe(self):
        if not self.subscriber:
            filters = (get_market_type_filter(self.market_map.market_type),)
            options = GrpcProgramAccountOptions(filters, self.commitment)
            self.subscriber = GrpcProgramAccountSubscriber(
                subscription_name=f"{market_type_to_string(self.market_map.market_type)}MarketMap",
                program=self.market_map.program,
                grpc_config=self.grpc_config,
                on_update=self.on_update,
                options=options,
                decode=self.decode,
            )

        await self.subscriber.subscribe()

    async def unsubscribe(self):
        if not self.subscriber:
            return
        await self.subscriber.unsubscribe()
        self.subscriber = None
