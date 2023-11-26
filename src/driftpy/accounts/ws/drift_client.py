from anchorpy import Program
from solders.pubkey import Pubkey
from solana.rpc.commitment import Commitment

from driftpy.accounts.types import DriftClientAccountSubscriber, DataAndSlot
from typing import Optional

from driftpy.accounts.ws.account_subscriber import WebsocketAccountSubscriber
from driftpy.types import (
    PerpMarketAccount,
    SpotMarketAccount,
    OraclePriceData,
    StateAccount,
)

from driftpy.addresses import *

from driftpy.types import OracleSource

from driftpy.accounts.oracle import decode_pyth_price_info, get_oracle_decode_fn


class WebsocketDriftClientAccountSubscriber(DriftClientAccountSubscriber):
    def __init__(self, program: Program, commitment: Commitment = "confirmed"):
        self.program = program
        self.commitment = commitment
        self.state_subscriber = None
        self.spot_market_subscribers = {}
        self.perp_market_subscribers = {}
        self.oracle_subscribers = {}

    async def subscribe(self):
        state_public_key = get_state_public_key(self.program.program_id)
        self.state_subscriber = WebsocketAccountSubscriber[StateAccount](
            state_public_key, self.program, self.commitment
        )
        await self.state_subscriber.subscribe()

        for i in range(self.state_subscriber.data_and_slot.data.number_of_spot_markets):
            await self.subscribe_to_spot_market(i)

        for i in range(self.state_subscriber.data_and_slot.data.number_of_markets):
            await self.subscribe_to_perp_market(i)

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

        spot_market = spot_market_subscriber.data_and_slot.data
        await self.subscribe_to_oracle(spot_market.oracle, spot_market.oracle_source)

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

        perp_market = perp_market_subscriber.data_and_slot.data
        await self.subscribe_to_oracle(
            perp_market.amm.oracle, perp_market.amm.oracle_source
        )

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
        self.state_subscriber.unsubscribe()
        for spot_market_subscriber in self.spot_market_subscribers.values():
            spot_market_subscriber.unsubscribe()
        for perp_market_subscriber in self.perp_market_subscribers.values():
            perp_market_subscriber.unsubscribe()
        for oracle_subscriber in self.oracle_subscribers.values():
            oracle_subscriber.unsubscribe()
