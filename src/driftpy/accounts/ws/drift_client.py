import asyncio

from anchorpy import Program
from solana.rpc.commitment import Commitment

from driftpy.accounts.types import DriftClientAccountSubscriber, DataAndSlot
from typing import Optional, Sequence

from driftpy.accounts.ws.account_subscriber import WebsocketAccountSubscriber
from driftpy.constants.config import find_all_market_and_oracles
from driftpy.types import (
    PerpMarketAccount,
    SpotMarketAccount,
    OraclePriceData,
    StateAccount,
    OracleInfo,
)

from driftpy.addresses import *

from driftpy.types import OracleSource

from driftpy.accounts.oracle import get_oracle_decode_fn

class WebsocketDriftClientAccountSubscriber(DriftClientAccountSubscriber):
    def __init__(
        self,
        program: Program,
        perp_market_indexes: Sequence[int],
        spot_market_indexes: Sequence[int],
        oracle_infos: Sequence[OracleInfo],
        should_find_all_markets_and_oracles: bool,
        commitment: Commitment = "confirmed",
    ):
        self.program = program
        self.commitment = commitment

        self.perp_market_indexes = perp_market_indexes
        self.spot_market_indexes = spot_market_indexes
        self.oracle_infos = oracle_infos
        self.should_find_all_markets_and_oracles = should_find_all_markets_and_oracles

        self.state_subscriber = None
        self.spot_market_subscribers = {}
        self.perp_market_subscribers = {}
        self.oracle_subscribers = {}

    async def subscribe(self):
        if self.is_subscribed():
            return

        state_public_key = get_state_public_key(self.program.program_id)
        self.state_subscriber = WebsocketAccountSubscriber[StateAccount](
            state_public_key, self.program, self.commitment
        )
        await self.state_subscriber.subscribe()

        if self.should_find_all_markets_and_oracles:
            (
                perp_market_indexes,
                spot_market_indexes,
                oracle_infos,
            ) = await find_all_market_and_oracles(self.program)
            self.perp_market_indexes = perp_market_indexes
            self.spot_market_indexes = spot_market_indexes
            self.oracle_infos = oracle_infos

        for perp_market_index in self.perp_market_indexes:
            await self.subscribe_to_perp_market(perp_market_index)

        for spot_market_index in self.spot_market_indexes:
            await self.subscribe_to_spot_market(spot_market_index)

        for oracle_info in self.oracle_infos:
            await self.subscribe_to_oracle(oracle_info.pubkey, oracle_info.source)

    async def subscribe_to_spot_market(self, market_index: int):
        if market_index in self.spot_market_subscribers:
            return

        spot_market_public_key = get_spot_market_public_key(
            self.program.program_id, market_index
        )
        spot_market_subscriber = WebsocketAccountSubscriber[SpotMarketAccount](
            spot_market_public_key, self.program, self.commitment
        )
        await spot_market_subscriber.subscribe()
        self.spot_market_subscribers[market_index] = spot_market_subscriber

    async def subscribe_to_perp_market(self, market_index: int):
        if market_index in self.perp_market_subscribers:
            return

        perp_market_public_key = get_perp_market_public_key(
            self.program.program_id, market_index
        )
        perp_market_subscriber = WebsocketAccountSubscriber[PerpMarketAccount](
            perp_market_public_key, self.program, self.commitment
        )
        await perp_market_subscriber.subscribe()
        self.perp_market_subscribers[market_index] = perp_market_subscriber

    async def subscribe_to_oracle(self, oracle: Pubkey, oracle_source: OracleSource):
        if oracle == Pubkey.default():
            return

        if str(oracle) in self.oracle_subscribers:
            return

        oracle_subscriber = WebsocketAccountSubscriber[OraclePriceData](
            oracle,
            self.program,
            self.commitment,
            get_oracle_decode_fn(oracle_source),
        )
        await oracle_subscriber.subscribe()
        self.oracle_subscribers[str(oracle)] = oracle_subscriber

    def is_subscribed(self):
        return (
            self.state_subscriber is not None and self.state_subscriber.is_subscribed()
        )

    async def fetch(self):
        if not self.is_subscribed():
            return

        tasks = [self.state_subscriber.fetch()]

        for perp_market_subscriber in self.perp_market_subscribers.values():
            tasks.append(perp_market_subscriber.fetch())

        for spot_market_subscriber in self.spot_market_subscribers.values():
            tasks.append(spot_market_subscriber.fetch())

        for oracle_subscriber in self.oracle_subscribers.values():
            tasks.append(oracle_subscriber.fetch())

        await asyncio.gather(*tasks)

    def get_state_account_and_slot(self) -> Optional[DataAndSlot[StateAccount]]:
        return self.state_subscriber.data_and_slot

    def get_perp_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[PerpMarketAccount]]:
        return self.perp_market_subscribers[market_index].data_and_slot

    def get_spot_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[SpotMarketAccount]]:
        return self.spot_market_subscribers[market_index].data_and_slot

    def get_oracle_price_data_and_slot(
        self, oracle: Pubkey
    ) -> Optional[DataAndSlot[OraclePriceData]]:
        return self.oracle_subscribers[str(oracle)].data_and_slot

    def unsubscribe(self):
        if self.is_subscribed():
            self.state_subscriber.unsubscribe()
            for spot_market_subscriber in self.spot_market_subscribers.values():
                spot_market_subscriber.unsubscribe()
            for perp_market_subscriber in self.perp_market_subscribers.values():
                perp_market_subscriber.unsubscribe()
            for oracle_subscriber in self.oracle_subscribers.values():
                oracle_subscriber.unsubscribe()
