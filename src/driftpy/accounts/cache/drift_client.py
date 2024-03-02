import asyncio
from typing import Awaitable, Callable, Optional

from anchorpy import Program

from solders.pubkey import Pubkey  # type: ignore

from solana.rpc.commitment import Commitment, Confirmed
from solana.rpc.core import RPCException

from driftpy.accounts.oracle import (
    get_oracle_price_data_and_slot,
)
from driftpy.accounts.types import DriftClientAccountSubscriber, DataAndSlot
from driftpy.accounts import (
    get_state_account_and_slot,
    get_spot_market_account_and_slot,
    get_perp_market_account_and_slot,
)
from driftpy.constants.config import get_oracle_source_for_oracle
from driftpy.constants.numeric_constants import QUOTE_SPOT_MARKET_INDEX
from driftpy.types import (
    MarketType,
    OracleInfo,
    PerpMarketAccount,
    SpotMarketAccount,
    OraclePriceData,
    StateAccount,
    GenericMarketType,
    logger,
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
        spot_markets = {}
        perp_markets = {}

        if self.should_find_all_markets_and_oracles:
            for i in range(state_and_slot.data.number_of_spot_markets):
                spot_market_and_slot = await get_spot_market_account_and_slot(
                    self.program, i
                )
                spot_markets[market_index] = spot_market_and_slot

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
                perp_markets[market_index] = perp_market_and_slot

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
                spot_markets[market_index] = spot_market_and_slot

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
                perp_markets[market_index] = perp_market_and_slot

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

    async def _add_perp_market_to_cache(self, market_index: int):
        try:
            perp_market_and_slot = await self.fetch_market_with_retry(
                get_perp_market_account_and_slot, self.program, market_index
            )
            if perp_market_and_slot:
                self.cache["perp_markets"][market_index] = perp_market_and_slot
                return True
            return False
        except RPCException:
            return False

    def get_perp_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[PerpMarketAccount]]:
        perp_market_and_slot = self.cache["perp_markets"].get(market_index, None)
        if perp_market_and_slot is None:
            logger.warning(
                f"DRIFTPY: Adding perp market {market_index} not found in cache"
            )
            future = asyncio.create_task(self._add_perp_market_to_cache(market_index))
            future.add_done_callback(lambda _: self._assert_perp_market(market_index))
            future.add_done_callback(
                lambda _: self._add_oracle_callback(market_index, MarketType.Perp())
            )
            return None
        return perp_market_and_slot

    async def _add_spot_market_to_cache(self, market_index: int):
        try:
            spot_market_and_slot = await self.fetch_market_with_retry(
                get_spot_market_account_and_slot, self.program, market_index
            )
            if spot_market_and_slot:
                self.cache["spot_markets"][market_index] = spot_market_and_slot
                return True
            return False
        except RPCException:
            return False

    def get_spot_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[SpotMarketAccount]]:
        spot_market_and_slot = self.cache["spot_markets"].get(market_index, None)
        if spot_market_and_slot is None:
            logger.warning(
                f"DRIFTPY: Adding spot market {market_index} not found in cache"
            )
            future = asyncio.create_task(self._add_spot_market_to_cache(market_index))
            future.add_done_callback(lambda _: self._assert_spot_market(market_index))
            future.add_done_callback(
                lambda _: self._add_oracle_callback(market_index, MarketType.Spot())
            )
            return None
        return spot_market_and_slot

    def _add_oracle_callback(self, market_index: int, market_type: MarketType):
        match market_type:
            case MarketType.Spot():
                if market_index > self.cache["state"].data.number_of_spot_markets:
                    return
            case MarketType.Perp():
                if market_index > self.cache["state"].data.number_of_markets:
                    return

        oracle = None
        match market_type:
            case MarketType.Spot():
                oracle = self.cache["spot_markets"][market_index].data.oracle
            case MarketType.Perp():
                oracle = self.cache["perp_markets"][market_index].data.amm.oracle

        if oracle in self.cache["oracle_price_data"]:
            return

        asyncio.create_task(self._add_oracle_to_cache_with_retry(oracle))

    async def _add_oracle_to_cache_with_retry(self, oracle: Pubkey):
        oracle_source = get_oracle_source_for_oracle(oracle)
        oracle_info = OracleInfo(oracle, oracle_source)
        if oracle_info in self.oracle_infos:
            return

        self.oracle_infos.append(oracle_info)
        delay = 1

        max_retries = 3
        while not (await self._add_oracle_to_cache(oracle_info)) and max_retries > 0:
            max_retries -= 1
            if max_retries == 0:
                return
            await asyncio.sleep(delay)
            delay *= 2

    async def _add_oracle_to_cache(self, oracle_info: OracleInfo):
        try:
            oracle_price_data_and_slot = await get_oracle_price_data_and_slot(
                self.program.provider.connection, oracle_info.pubkey, oracle_info.source
            )
            if oracle_price_data_and_slot:
                self.cache["oracle_price_data"][
                    str(oracle_info.pubkey)
                ] = oracle_price_data_and_slot
                return True
            return False
        except RPCException:
            return False

    def get_oracle_price_data_and_slot(
        self, oracle: Pubkey
    ) -> Optional[DataAndSlot[OraclePriceData]]:
        oracle_price_data_and_slot = self.cache["oracle_price_data"].get(
            str(oracle), None
        )
        if oracle_price_data_and_slot is None:
            logger.warning(f"DRIFTPY: Adding oracle {oracle} not found in cache")
            future = asyncio.create_task(self._add_oracle_to_cache_with_retry(oracle))
            future.add_done_callback(lambda _: self._assert_oracle(oracle))
            return None
        return oracle_price_data_and_slot

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

    def get_market_accounts_and_slots(self) -> list[DataAndSlot[PerpMarketAccount]]:
        return list(self.cache["perp_markets"].values())

    def get_spot_market_accounts_and_slots(
        self,
    ) -> list[DataAndSlot[SpotMarketAccount]]:
        return list(self.cache["spot_markets"].values())

    def _assert_perp_market(self, market_index: int):
        if (
            self.cache["perp_markets"].get(market_index, None) is None
            and market_index < self.cache["state"].data.number_of_markets
        ):
            logger.warning(
                f"DRIFTPY: Perp market {market_index} not found in cache after adding"
            )

    def _assert_spot_market(self, market_index: int):
        if (
            self.cache["spot_markets"].get(market_index, None) is None
            and market_index < self.cache["state"].data.number_of_spot_markets
        ):
            logger.warning(
                f"DRIFTPY: Spot market {market_index} not found in cache after adding"
            )

    def _assert_oracle(self, oracle: Pubkey):
        if self.cache["oracle_price_data"].get(str(oracle), None) is None:
            logger.warning(f"DRIFTPY: Oracle {oracle} not found in cache after adding")

    async def fetch_market_with_retry(
        self,
        fetcher: Callable[[Program, int], Awaitable[Optional[GenericMarketType]]],
        program: Program,
        market_index: int,
        retries: int = 3,
    ) -> Optional[GenericMarketType]:
        """
        Fetch a perp / spot market from the program with retries

        Params:
        `fetcher`: Callable[[Program, int], Awaitable[Optional[GenericMarketType]]] - the function to fetch the market
        `program`: Program - the drift Program object
        `market_index`: int - the index of the market to fetch
        `retries`: int - the number of retries to attempt fetching the market (default 3)
        """
        retries = 3
        delay = 1
        while retries > 0:
            try:
                data = await fetcher(program, market_index)
                if data:
                    return data
            except RPCException as e:
                logger.warning(
                    f"DRIFTPY: Error fetching data for market {market_index}: {e}, retrying"
                )
                await asyncio.sleep(delay)
                delay *= 2
                retries -= 1

        logger.error(
            f"DRIFTPY: Failed to fetch data for market {market_index} after 3 retries"
        )
        return None

    async def unsubscribe(self):
        self.cache = None
