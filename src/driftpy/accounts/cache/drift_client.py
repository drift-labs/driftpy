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

from driftpy.types import PerpMarket, SpotMarket, OraclePriceData, State


class CachedDriftClientAccountSubscriber(DriftClientAccountSubscriber):
    def __init__(self, program: Program, commitment: Commitment = "confirmed"):
        self.program = program
        self.commitment = commitment
        self.cache = None

    async def update_cache(self):
        if self.cache is None:
            self.cache = {}

        state_and_slot = await get_state_account_and_slot(self.program)
        self.cache["state"] = state_and_slot

        oracle_data = {}

        spot_markets = []
        for i in range(state_and_slot.data.number_of_spot_markets):
            spot_market_and_slot = await get_spot_market_account_and_slot(
                self.program, i
            )
            spot_markets.append(spot_market_and_slot)

            oracle_price_data_and_slot = await get_oracle_price_data_and_slot(
                self.program.provider.connection,
                spot_market_and_slot.data.oracle,
                spot_market_and_slot.data.oracle_source,
            )
            oracle_data[
                str(spot_market_and_slot.data.oracle)
            ] = oracle_price_data_and_slot

        self.cache["spot_markets"] = spot_markets

        perp_markets = []
        for i in range(state_and_slot.data.number_of_markets):
            perp_market_and_slot = await get_perp_market_account_and_slot(
                self.program, i
            )
            perp_markets.append(perp_market_and_slot)

            oracle_price_data_and_slot = await get_oracle_price_data_and_slot(
                self.program.provider.connection,
                perp_market_and_slot.data.amm.oracle,
                perp_market_and_slot.data.amm.oracle_source,
            )
            oracle_data[
                str(perp_market_and_slot.data.amm.oracle)
            ] = oracle_price_data_and_slot

        self.cache["perp_markets"] = perp_markets

        self.cache["oracle_price_data"] = oracle_data

    async def get_state_account_and_slot(self) -> Optional[DataAndSlot[State]]:
        await self.cache_if_needed()
        return self.cache["state"]

    async def get_perp_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[PerpMarket]]:
        await self.cache_if_needed()
        return self.cache["perp_markets"][market_index]

    async def get_spot_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[SpotMarket]]:
        await self.cache_if_needed()
        return self.cache["spot_markets"][market_index]

    async def get_oracle_data_and_slot(
        self, oracle: Pubkey
    ) -> Optional[DataAndSlot[OraclePriceData]]:
        await self.cache_if_needed()
        return self.cache["oracle_price_data"][str(oracle)]

    async def cache_if_needed(self):
        if self.cache is None:
            await self.update_cache()
