import asyncio
from anchorpy import Program
from solders.pubkey import Pubkey
from solana.rpc.commitment import Commitment

from driftpy.accounts import (
    get_state_account_and_slot,
)
from driftpy.accounts.get_accounts import get_spot_market_account_and_slot, get_perp_market_account_and_slot
from driftpy.accounts.oracle import get_oracle_price_data_and_slot, oracle_ai_to_oracle_price_data
from driftpy.accounts.types import DriftClientAccountSubscriber, DataAndSlot
from typing import Optional
from driftpy.types import (
    PerpMarketAccount,
    SpotMarketAccount,
    OraclePriceData,
    StateAccount,
)


class DemoDriftClientAccountSubscriber(DriftClientAccountSubscriber):
    def __init__(self, program: Program, perp_market_indexes, spot_market_indexes, commitment: Commitment = "confirmed"):
        self.program = program
        self.perp_market_indexes = perp_market_indexes
        self.spot_market_indexes = spot_market_indexes
        self.commitment = commitment
        self.cache = None

    async def subscribe(self):
        await self.update_cache()

    async def update_cache(self):
        if self.cache is None:
            self.cache = {}

        state_and_slot = await get_state_account_and_slot(self.program)
        self.cache["state"] = state_and_slot

        oracle_data: dict[str, DataAndSlot[OraclePriceData]] = {}
        spot_markets: list[DataAndSlot[SpotMarketAccount]] = []
        perp_markets: list[DataAndSlot[PerpMarketAccount]] = []

        # print(self.spot_market_indexes)
        # print(self.perp_market_indexes)

        for index in self.spot_market_indexes:
            spot_market_and_slot = await get_spot_market_account_and_slot(self.program, index)
            spot_markets.append(spot_market_and_slot)

        spot_market_oracle_pubkeys = [spot_market.data.oracle for spot_market in spot_markets]

        spot_market_oracle_accounts = await self.program.provider.connection.get_multiple_accounts(spot_market_oracle_pubkeys)

        for i, oracle_ai in enumerate(spot_market_oracle_accounts.value):
            oracle_price_data_and_slot = oracle_ai_to_oracle_price_data(oracle_ai, spot_markets[i].data.oracle_source)
            oracle_data[str(spot_market_oracle_pubkeys[i])] = oracle_price_data_and_slot

        for index in self.perp_market_indexes:
            perp_market_and_slot = await get_perp_market_account_and_slot(self.program, index)
            perp_markets.append(perp_market_and_slot)

        perp_market_oracle_pubkeys = [perp_market.data.amm.oracle for perp_market in perp_markets]

        perp_market_oracle_accounts = await self.program.provider.connection.get_multiple_accounts(perp_market_oracle_pubkeys)

        for i, oracle_ai in enumerate(perp_market_oracle_accounts.value):
            oracle_price_data_and_slot = oracle_ai_to_oracle_price_data(oracle_ai, perp_markets[i].data.amm.oracle_source)
            oracle_data[str(perp_market_oracle_pubkeys[i])] = oracle_price_data_and_slot

        self.cache["spot_markets"] = spot_markets
        self.cache["perp_markets"] = perp_markets
        self.cache["oracle_price_data"] = oracle_data

    async def fetch(self):
        await self.update_cache()

    def get_state_account_and_slot(self) -> Optional[DataAndSlot[StateAccount]]:
        return self.cache["state"]

    def get_perp_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[PerpMarketAccount]]:
        return self.cache["perp_markets"][market_index]

    def get_spot_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[SpotMarketAccount]]:
        return self.cache["spot_markets"][market_index]

    def get_oracle_price_data_and_slot(
        self, oracle: Pubkey
    ) -> Optional[DataAndSlot[OraclePriceData]]:
        return self.cache["oracle_price_data"][str(oracle)]

    def unsubscribe(self):
        self.cache = None
