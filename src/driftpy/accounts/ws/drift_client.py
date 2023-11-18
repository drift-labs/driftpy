from anchorpy import Program
from solders.pubkey import Pubkey
from solana.rpc.commitment import Commitment

from driftpy.accounts import (
    get_state_account_and_slot,
    get_spot_market_account_and_slot,
    get_perp_market_account_and_slot,
)
from driftpy.accounts.oracle import get_oracle_price_data_and_slot
from driftpy.accounts.types import DriftClientAccountSubscriber, DataAndSlot
from typing import Optional

from driftpy.accounts.ws.account_subscriber import WebsocketAccountSubscriber
from driftpy.types import PerpMarket, SpotMarket, OraclePriceData, State

from driftpy.addresses import *

from driftpy.types import OracleSource

from driftpy.accounts.oracle import decode_pyth_price_info


class WebsocketDriftClientAccountSubscriber:
    def __init__(self, program: Program, commitment: Commitment = "confirmed"):
        self.program = program
        self.commitment = commitment
        self.state_subscriber = None
        self.spot_market_subscribers = []
        self.perp_market_subscribers = []
        self.oracle_subscribers = {}

    async def subscribe(self):
        state_public_key = get_state_public_key(self.program.program_id)
        self.state_subscriber = WebsocketAccountSubscriber[State](
            state_public_key, self.program, self.commitment
        )
        await self.state_subscriber.subscribe()

        for i in range(self.state_subscriber.data_and_slot.data.number_of_spot_markets):
            spot_market_public_key = get_spot_market_public_key(
                self.program.program_id, i
            )
            spot_market_subscriber = WebsocketAccountSubscriber[SpotMarket](
                spot_market_public_key, self.program, self.commitment
            )
            await spot_market_subscriber.subscribe()
            self.spot_market_subscribers.append(spot_market_subscriber)

            spot_market = spot_market_subscriber.data_and_slot.data
            oracle = spot_market.oracle
            if oracle != Pubkey.default():
                oracle_subscriber = WebsocketAccountSubscriber[OraclePriceData](
                    oracle,
                    self.program,
                    self.commitment,
                    self._get_oracle_decode_fn(spot_market.oracle_source),
                )
                await oracle_subscriber.subscribe()
                self.oracle_subscribers[str(oracle)] = oracle_subscriber

        for i in range(self.state_subscriber.data_and_slot.data.number_of_markets):
            perp_market_public_key = get_perp_market_public_key(
                self.program.program_id, i
            )
            perp_market_subscriber = WebsocketAccountSubscriber[PerpMarket](
                perp_market_public_key, self.program, self.commitment
            )
            await perp_market_subscriber.subscribe()
            self.perp_market_subscribers.append(perp_market_subscriber)

            perp_market = perp_market_subscriber.data_and_slot.data
            oracle = perp_market.amm.oracle
            oracle_subscriber = WebsocketAccountSubscriber[OraclePriceData](
                oracle,
                self.program,
                self.commitment,
                self._get_oracle_decode_fn(perp_market.amm.oracle_source),
            )
            await oracle_subscriber.subscribe()
            self.oracle_subscribers[str(oracle)] = oracle_subscriber

    def _get_oracle_decode_fn(self, oracle_source: OracleSource):
        if "Pyth" in str(oracle_source):
            return lambda data: decode_pyth_price_info(data, oracle_source)
        else:
            raise Exception("Unknown oracle source")

    async def get_state_account_and_slot(self) -> Optional[DataAndSlot[State]]:
        return self.state_subscriber.data_and_slot

    async def get_perp_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[PerpMarket]]:
        return self.perp_market_subscribers[market_index].data_and_slot

    async def get_spot_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[SpotMarket]]:
        return self.spot_market_subscribers[market_index].data_and_slot

    async def get_oracle_price_data_and_slot(
        self, oracle: Pubkey
    ) -> Optional[DataAndSlot[OraclePriceData]]:
        return self.oracle_subscribers[str(oracle)].data_and_slot
