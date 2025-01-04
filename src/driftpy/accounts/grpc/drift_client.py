from typing import Sequence

from anchorpy.program.core import Program
from solana.rpc.commitment import Commitment
from solders.pubkey import Pubkey

from driftpy.accounts.grpc.account_subscriber import GrpcAccountSubscriber, GrpcConfig
from driftpy.accounts.oracle import get_oracle_decode_fn
from driftpy.accounts.types import FullOracleWrapper
from driftpy.accounts.ws.drift_client import WebsocketDriftClientAccountSubscriber
from driftpy.addresses import (
    get_perp_market_public_key,
    get_spot_market_public_key,
    get_state_public_key,
)
from driftpy.constants.config import find_all_market_and_oracles
from driftpy.market_map.grpc_market_map import GrpcMarketMap
from driftpy.market_map.market_map_config import GrpcMarketMapConfig
from driftpy.oracles.oracle_id import get_oracle_id
from driftpy.types import (
    MarketType,
    OraclePriceData,
    PerpMarketAccount,
    SpotMarketAccount,
    StateAccount,
)


class GrpcDriftClientAccountSubscriber(WebsocketDriftClientAccountSubscriber):
    def __init__(
        self,
        program: Program,
        grpc_config: GrpcConfig,
        perp_market_indexes: Sequence[int],
        spot_market_indexes: Sequence[int],
        full_oracle_wrappers: Sequence[FullOracleWrapper],
        should_find_all_markets_and_oracles: bool,
        commitment: Commitment = Commitment("confirmed"),
    ):
        super().__init__(
            program,
            perp_market_indexes,
            spot_market_indexes,
            full_oracle_wrappers,
            should_find_all_markets_and_oracles,
            commitment,
        )
        self.grpc_config = grpc_config

    async def subscribe_to_spot_market(self, market_index: int):
        if market_index in self.spot_market_subscribers:
            return

        spot_market_public_key = get_spot_market_public_key(
            self.program.program_id, market_index
        )
        spot_market_subscriber = GrpcAccountSubscriber[SpotMarketAccount](
            self.grpc_config,
            f"spot_market_{market_index}",
            self.program,
            spot_market_public_key,
            self.commitment,
        )
        await spot_market_subscriber.subscribe()
        self.spot_market_subscribers[market_index] = spot_market_subscriber

    async def subscribe_to_perp_market(self, market_index: int):
        if market_index in self.perp_market_subscribers:
            return

        perp_market_public_key = get_perp_market_public_key(
            self.program.program_id, market_index
        )
        perp_market_subscriber = GrpcAccountSubscriber[PerpMarketAccount](
            self.grpc_config,
            f"perp_market_{market_index}",
            self.program,
            perp_market_public_key,
            self.commitment,
        )
        await perp_market_subscriber.subscribe()
        self.perp_market_subscribers[market_index] = perp_market_subscriber

    async def subscribe_to_oracle(self, full_oracle_wrapper: FullOracleWrapper):
        if full_oracle_wrapper.pubkey == Pubkey.default():
            return

        oracle_id = get_oracle_id(
            full_oracle_wrapper.pubkey,
            full_oracle_wrapper.oracle_source,
        )
        if oracle_id in self.oracle_subscribers:
            return

        oracle_subscriber = GrpcAccountSubscriber[OraclePriceData](
            self.grpc_config,
            f"oracle_{oracle_id}",
            self.program,
            full_oracle_wrapper.pubkey,
            self.commitment,
            decode=get_oracle_decode_fn(full_oracle_wrapper.oracle_source),
            initial_data=full_oracle_wrapper.oracle_price_data_and_slot,
        )

        await oracle_subscriber.subscribe()
        self.oracle_subscribers[oracle_id] = oracle_subscriber

    async def subscribe(self):
        if self.is_subscribed():
            return

        state_public_key = get_state_public_key(self.program.program_id)
        self.state_subscriber = GrpcAccountSubscriber[StateAccount](
            self.grpc_config,
            "state",
            self.program,
            state_public_key,
            self.commitment,
        )
        await self.state_subscriber.subscribe()

        if self.should_find_all_markets_and_oracles:
            (
                perp_ds,
                spot_ds,
                full_oracle_wrappers,
            ) = await find_all_market_and_oracles(self.program)

            self.perp_market_indexes = [
                data_and_slot.data.market_index for data_and_slot in perp_ds
            ]
            self.spot_market_indexes = [
                data_and_slot.data.market_index for data_and_slot in spot_ds
            ]
            self.full_oracle_wrappers = full_oracle_wrappers

            spot_market_config = GrpcMarketMapConfig(
                program=self.program,
                market_type=MarketType.Spot(),  # type: ignore
                grpc_config=self.grpc_config,
                connection=self.program.provider.connection,
            )

            perp_market_config = GrpcMarketMapConfig(
                program=self.program,
                market_type=MarketType.Perp(),  # type: ignore
                grpc_config=self.grpc_config,
                connection=self.program.provider.connection,
            )

            spot_market_map = GrpcMarketMap(spot_market_config)
            perp_market_map = GrpcMarketMap(perp_market_config)

            spot_market_map.init(spot_ds)
            perp_market_map.init(perp_ds)

            self.spot_market_map = spot_market_map
            self.perp_market_map = perp_market_map

            await spot_market_map.subscribe()
            await perp_market_map.subscribe()

            for full_oracle_wrapper in self.full_oracle_wrappers:
                await self.subscribe_to_oracle(full_oracle_wrapper)

            for market_index in self.perp_market_indexes:
                await self.subscribe_to_perp_market(market_index)

            for market_index in self.spot_market_indexes:
                await self.subscribe_to_spot_market(market_index)
        else:
            for market_index in self.perp_market_indexes:
                await self.subscribe_to_perp_market(market_index)

            for market_index in self.spot_market_indexes:
                await self.subscribe_to_spot_market(market_index)

            for full_oracle_wrapper in self.full_oracle_wrappers:
                await self.subscribe_to_oracle(full_oracle_wrapper)

        await self._set_perp_oracle_map()
        await self._set_spot_oracle_map()
        await self.fetch()

    async def unsubscribe(self):
        if self.is_subscribed():
            await self.state_subscriber.unsubscribe()
            if self.spot_market_map and self.perp_market_map:
                await self.spot_market_map.unsubscribe()
                await self.perp_market_map.unsubscribe()
            else:
                for spot_market_subscriber in self.spot_market_subscribers.values():
                    await spot_market_subscriber.unsubscribe()
                for perp_market_subscriber in self.perp_market_subscribers.values():
                    await perp_market_subscriber.unsubscribe()
            for oracle_subscriber in self.oracle_subscribers.values():
                await oracle_subscriber.unsubscribe()
