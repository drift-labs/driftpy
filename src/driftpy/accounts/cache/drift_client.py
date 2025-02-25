from typing import Optional, TypedDict, TypeVar

from anchorpy import Program
from solana.rpc.commitment import Commitment, Confirmed

from driftpy.accounts import (
    DataAndSlot,
    get_perp_market_account_and_slot,
    get_spot_market_account_and_slot,
    get_state_account_and_slot,
)
from driftpy.accounts.oracle import get_oracle_price_data_and_slot
from driftpy.accounts.types import DataAndSlot, DriftClientAccountSubscriber
from driftpy.constants.numeric_constants import QUOTE_SPOT_MARKET_INDEX
from driftpy.oracles.oracle_id import get_oracle_id
from driftpy.types import (
    OracleInfo,
    OraclePriceData,
    PerpMarketAccount,
    SpotMarketAccount,
    StateAccount,
    stack_trace,
)

T = TypeVar("T", PerpMarketAccount, SpotMarketAccount)


class DriftClientCache(TypedDict):
    perp_markets: list[DataAndSlot[PerpMarketAccount]]
    spot_markets: list[DataAndSlot[SpotMarketAccount]]
    oracle_price_data: dict[str, OraclePriceData]
    state: DataAndSlot[StateAccount] | None


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
        self.cache: DriftClientCache = {
            "spot_markets": [],
            "perp_markets": [],
            "oracle_price_data": {},
            "state": None,
        }
        self.perp_market_indexes = perp_market_indexes
        self.spot_market_indexes = spot_market_indexes
        self.oracle_infos = oracle_infos
        self.should_find_all_markets_and_oracles = should_find_all_markets_and_oracles

    async def subscribe(self):
        await self.update_cache()

    async def update_cache(self):
        is_empty = all(not d for d in self.cache.values())
        if is_empty:
            self.cache = {
                "spot_markets": [],
                "perp_markets": [],
                "oracle_price_data": {},
                "state": None,
            }

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
                if spot_market_and_slot is None:
                    raise ValueError(
                        f"Spot market {i} not found, Location: {stack_trace()}"
                    )

                spot_markets.append(spot_market_and_slot)

                oracle_price_data_and_slot = await get_oracle_price_data_and_slot(
                    self.program.provider.connection,
                    spot_market_and_slot.data.oracle,
                    spot_market_and_slot.data.oracle_source,
                )
                oracle_id = get_oracle_id(
                    spot_market_and_slot.data.oracle,
                    spot_market_and_slot.data.oracle_source,
                )
                oracle_data[oracle_id] = oracle_price_data_and_slot

            self.cache["spot_markets"] = spot_markets

            for i in range(state_and_slot.data.number_of_markets):
                perp_market_and_slot = await get_perp_market_account_and_slot(
                    self.program, i
                )
                if perp_market_and_slot is None:
                    raise ValueError(
                        f"Perp market {i} not found, Location: {stack_trace()}"
                    )

                perp_markets.append(perp_market_and_slot)

                oracle_price_data_and_slot = await get_oracle_price_data_and_slot(
                    self.program.provider.connection,
                    perp_market_and_slot.data.amm.oracle,
                    perp_market_and_slot.data.amm.oracle_source,
                )
                oracle_id = get_oracle_id(
                    perp_market_and_slot.data.amm.oracle,
                    perp_market_and_slot.data.amm.oracle_source,
                )
                oracle_data[oracle_id] = oracle_price_data_and_slot

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
                    oracle_id = get_oracle_id(
                        spot_market_and_slot.data.oracle,
                        spot_market_and_slot.data.oracle_source,
                    )
                    oracle_data[oracle_id] = oracle_price_data_and_slot

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
                    oracle_id = get_oracle_id(
                        perp_market_and_slot.data.amm.oracle,
                        perp_market_and_slot.data.amm.oracle_source,
                    )
                    oracle_data[oracle_id] = oracle_price_data_and_slot

            self.cache["perp_markets"] = perp_markets

            self.cache["oracle_price_data"] = oracle_data

    async def fetch(self):
        await self.update_cache()

    def resurrect(
        self,
        spot_markets,  # MarketMap
        perp_markets,  # MarketMap
        spot_oracles: dict[int, OraclePriceData],
        perp_oracles: dict[int, OraclePriceData],
    ):
        def sort_markets(
            markets: dict[int, T],  # where T is the specific market type
        ) -> list[T]:
            return sorted(markets.values(), key=lambda market: market.data.market_index)

        self.cache["spot_markets"] = sort_markets(spot_markets)  # SpotMarketAccount
        self.cache["perp_markets"] = sort_markets(perp_markets)  # PerpMarketAccount

        for market_index, oracle_price_data in spot_oracles.items():
            corresponding_market = self.cache["spot_markets"][market_index]
            oracle_pubkey = corresponding_market.data.oracle
            oracle_source = corresponding_market.data.oracle_source
            oracle_id = get_oracle_id(oracle_pubkey, oracle_source)
            self.cache["oracle_price_data"][oracle_id] = oracle_price_data

        for market_index, oracle_price_data in perp_oracles.items():
            corresponding_market = self.cache["perp_markets"][market_index]
            oracle_pubkey = corresponding_market.data.amm.oracle
            oracle_source = corresponding_market.data.amm.oracle_source
            oracle_id = get_oracle_id(
                oracle_pubkey,
                oracle_source,
            )
            self.cache["oracle_price_data"][oracle_id] = oracle_price_data

    def get_state_account_and_slot(self) -> Optional[DataAndSlot[StateAccount]]:
        return self.cache["state"]

    def get_perp_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[PerpMarketAccount]]:
        try:
            for market in self.cache["perp_markets"]:
                if market.data.market_index == market_index:
                    return market
            return None
        except IndexError:
            print(
                f"WARNING: Perp market {market_index} not found in cache, Location: {stack_trace()}"
            )
            return None

    def get_spot_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[SpotMarketAccount]]:
        try:
            for market in self.cache["spot_markets"]:
                if market.data.market_index == market_index:
                    return market
            return None
        except IndexError:
            print(
                f"WARNING: Spot market {market_index} not found in cache Location: {stack_trace()}"
            )
            return None

    def get_oracle_price_data_and_slot(
        self, oracle_id: str
    ) -> Optional[DataAndSlot[OraclePriceData]]:
        try:
            return self.cache["oracle_price_data"][oracle_id]
        except KeyError:
            print(
                f"WARNING: Oracle {oracle_id} not found in cache, Location: {stack_trace()}"
            )
            return None

    def get_oracle_price_data_and_slot_for_perp_market(
        self, market_index: int
    ) -> Optional[OraclePriceData]:
        perp_market = self.get_perp_market_and_slot(market_index)
        if perp_market:
            oracle = perp_market.data.amm.oracle
            oracle_id = get_oracle_id(oracle, perp_market.data.amm.oracle_source)
            return self.get_oracle_price_data_and_slot(oracle_id)
        return None

    def get_oracle_price_data_and_slot_for_spot_market(
        self, market_index: int
    ) -> Optional[OraclePriceData]:
        spot_market = self.get_spot_market_and_slot(market_index)
        if spot_market:
            oracle = spot_market.data.oracle
            oracle_id = get_oracle_id(oracle, spot_market.data.oracle_source)
            return self.get_oracle_price_data_and_slot(oracle_id)
        return None

    async def unsubscribe(self):
        self.cache = {
            "spot_markets": [],
            "perp_markets": [],
            "oracle_price_data": {},
            "state": None,
        }

    def get_market_accounts_and_slots(self) -> list[DataAndSlot[PerpMarketAccount]]:
        return self.cache["perp_markets"]

    def get_spot_market_accounts_and_slots(
        self,
    ) -> list[DataAndSlot[SpotMarketAccount]]:
        return self.cache["spot_markets"]
