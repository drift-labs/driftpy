from typing import Optional

from anchorpy import Program

from solders.pubkey import Pubkey  # type: ignore

from solana.rpc.commitment import Commitment, Confirmed

from driftpy.accounts.oracle import get_oracle_price_data_and_slot
from driftpy.accounts.types import DriftClientAccountSubscriber, DataAndSlot
from driftpy.accounts import (
    get_state_account_and_slot,
    get_spot_market_account_and_slot,
    get_perp_market_account_and_slot,
)
from driftpy.constants.numeric_constants import QUOTE_SPOT_MARKET_INDEX
from driftpy.types import (
    OracleInfo,
    PerpMarketAccount,
    SpotMarketAccount,
    OraclePriceData,
    StateAccount,
    stack_trace,
)


class CachedDriftClientAccountSubscriber(DriftClientAccountSubscriber):
    def __init__(
        self,
        program: Program,
        perp_market_indexes: list[int],
        spot_market_indexes: list[int],
        oracle_infos: list[OracleInfo],
        should_find_all_markets_and_oracles: bool = True,
        commitment: Commitment = Confirmed,
    ):
        self.program = program
        self.commitment = commitment
        self.cache = None
        self.perp_market_indexes = perp_market_indexes
        self.spot_market_indexes = spot_market_indexes
        self.oracle_infos = oracle_infos
        self.should_find_all_markets_and_oracles = should_find_all_markets_and_oracles

    async def subscribe(self):
        await self.update_cache()

    async def update_cache(self):
        if self.cache is None:
            self.cache = {}

        state_and_slot = await get_state_account_and_slot(self.program)
        self.cache["state"] = state_and_slot

        oracle_data = {}
        spot_markets = []
        perp_markets = []

        if self.should_find_all_markets_and_oracles:
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
        else:
            # force quote spot market
            if 0 not in self.spot_market_indexes:
                self.spot_market_indexes.insert(0, 0)

            for market_index in sorted(self.spot_market_indexes):
                spot_market_and_slot = await get_spot_market_account_and_slot(
                    self.program, market_index
                )
                spot_markets.append(spot_market_and_slot)

                if (
                    any(
                        info.pubkey == spot_market_and_slot.data.oracle
                        for info in self.oracle_infos
                    )
                    or market_index == QUOTE_SPOT_MARKET_INDEX
                ):  # if quote market forced, we won't have the oracle info
                    oracle_price_data_and_slot = await get_oracle_price_data_and_slot(
                        self.program.provider.connection,
                        spot_market_and_slot.data.oracle,
                        spot_market_and_slot.data.oracle_source,
                    )
                    oracle_data[
                        str(spot_market_and_slot.data.oracle)
                    ] = oracle_price_data_and_slot

            self.cache["spot_markets"] = spot_markets

            for market_index in sorted(self.perp_market_indexes):
                perp_market_and_slot = await get_perp_market_account_and_slot(
                    self.program, market_index
                )
                perp_markets.append(perp_market_and_slot)

                if any(
                    info.pubkey == perp_market_and_slot.data.amm.oracle
                    for info in self.oracle_infos
                ):
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

    async def fetch(self):
        await self.update_cache()

    def get_state_account_and_slot(self) -> Optional[DataAndSlot[StateAccount]]:
        return self.cache["state"]

    def get_perp_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[PerpMarketAccount]]:
        try:
            return self.cache["perp_markets"][market_index]
        except IndexError:
            print(
                f"WARNING: Perp market {market_index} not found in cache, Location: {stack_trace()}"
            )
            return None

    def get_spot_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[SpotMarketAccount]]:
        try:
            return self.cache["spot_markets"][market_index]
        except IndexError:
            print(
                f"WARNING: Spot market {market_index} not found in cache Location: {stack_trace()}"
            )
            return None

    def get_oracle_price_data_and_slot(
        self, oracle: Pubkey
    ) -> Optional[DataAndSlot[OraclePriceData]]:
        try:
            return self.cache["oracle_price_data"][str(oracle)]
        except KeyError:
            print(
                f"WARNING: Oracle {oracle} not found in cache, Location: {stack_trace()}"
            )
            return None

    def get_oracle_price_data_and_slot_for_perp_market(
        self, market_index: int
    ) -> Optional[OraclePriceData]:
        perp_market = self.get_perp_market_and_slot(market_index)
        if perp_market:
            oracle = perp_market.data.amm.oracle
            return self.get_oracle_price_data_and_slot(oracle)
        return None

    def get_oracle_price_data_and_slot_for_spot_market(
        self, market_index: int
    ) -> Optional[OraclePriceData]:
        spot_market = self.get_spot_market_and_slot(market_index)
        if spot_market:
            oracle = spot_market.data.oracle
            return self.get_oracle_price_data_and_slot(oracle)
        return None

    async def unsubscribe(self):
        self.cache = None

    def get_market_accounts_and_slots(self) -> list[DataAndSlot[PerpMarketAccount]]:
        return self.cache["perp_markets"]

    def get_spot_market_accounts_and_slots(
        self,
    ) -> list[DataAndSlot[SpotMarketAccount]]:
        return self.cache["spot_markets"]
