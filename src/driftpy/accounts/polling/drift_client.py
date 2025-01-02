import asyncio
from typing import Optional, Sequence, Union

from anchorpy.program.core import Program
from solders.pubkey import Pubkey

from driftpy.accounts import DataAndSlot, DriftClientAccountSubscriber
from driftpy.accounts.bulk_account_loader import BulkAccountLoader
from driftpy.accounts.oracle import get_oracle_decode_fn
from driftpy.addresses import (
    get_perp_market_public_key,
    get_spot_market_public_key,
    get_state_public_key,
)
from driftpy.constants.config import find_all_market_and_oracles_no_data_and_slots
from driftpy.oracles.oracle_id import get_oracle_id
from driftpy.types import (
    OracleInfo,
    OraclePriceData,
    OracleSource,
    PerpMarketAccount,
    SpotMarketAccount,
    StateAccount,
    stack_trace,
)


class PollingDriftClientAccountSubscriber(DriftClientAccountSubscriber):
    def __init__(
        self,
        program: Program,
        bulk_account_loader: BulkAccountLoader,
        perp_market_indexes: Sequence[int],
        spot_market_indexes: Sequence[int],
        oracle_infos: Sequence[OracleInfo],
        should_find_all_markets_and_oracles: bool,
    ):
        self.bulk_account_loader = bulk_account_loader
        self.program = program
        self.is_subscribed = False
        self.callbacks: dict[str, int] = {}
        self.oracle_callbacks: dict[str, int] = {}

        self.perp_market_indexes = perp_market_indexes
        self.spot_market_indexes = spot_market_indexes
        self.oracle_infos = oracle_infos
        self.should_find_all_markets_and_oracles = should_find_all_markets_and_oracles

        self.state: Optional[DataAndSlot[StateAccount]] = None
        self.perp_markets = {}
        self.spot_markets = {}
        self.oracle = {}
        self.perp_oracle_map: dict[int, Pubkey] = {}
        self.perp_oracle_strings_map: dict[int, str] = {}
        self.spot_oracle_map: dict[int, Pubkey] = {}
        self.spot_oracle_strings_map: dict[int, str] = {}

    async def subscribe(self):
        if len(self.callbacks) != 0:
            return

        if self.should_find_all_markets_and_oracles:
            (
                perp_market_indexes,
                spot_market_indexes,
                oracle_infos,
            ) = await find_all_market_and_oracles_no_data_and_slots(self.program)
            self.perp_market_indexes = perp_market_indexes
            self.spot_market_indexes = spot_market_indexes
            self.oracle_infos = oracle_infos

        await self.update_accounts_to_poll()

        while self.accounts_ready() is False:
            await self.bulk_account_loader.load()

        await self._set_perp_oracle_map()
        await self._set_spot_oracle_map()

    async def fetch(self):
        await self.bulk_account_loader.load()

    def accounts_ready(self) -> bool:
        return self.state is not None

    async def update_accounts_to_poll(self):
        state_public_key = get_state_public_key(self.program.program_id)
        state_callback_id = self.bulk_account_loader.add_account(
            state_public_key, self._get_state_callback()
        )
        self.callbacks[str(state_public_key)] = state_callback_id

        for perp_market_index in self.perp_market_indexes:
            pubkey = get_perp_market_public_key(
                self.program.program_id, perp_market_index
            )
            callback_id = self.bulk_account_loader.add_account(
                pubkey, self._get_perp_market_callback(perp_market_index)
            )
            self.callbacks[str(pubkey)] = callback_id

        for spot_market_index in self.spot_market_indexes:
            pubkey = get_spot_market_public_key(
                self.program.program_id, spot_market_index
            )
            callback_id = self.bulk_account_loader.add_account(
                pubkey, self._get_spot_market_callback(spot_market_index)
            )
            self.callbacks[str(pubkey)] = callback_id

        for oracle_info in self.oracle_infos:
            await self.add_oracle(oracle_info.pubkey, oracle_info.source)

    def _get_state_callback(self):
        def cb(buffer: bytes, slot: int):
            if buffer is None:
                return

            decoded_data = self.program.coder.accounts.decode(buffer)
            self.state = DataAndSlot(slot, decoded_data)

        return cb

    def _get_perp_market_callback(self, market_index: int):
        def cb(buffer: bytes, slot: int):
            if buffer is None:
                return

            decoded_data = self.program.coder.accounts.decode(buffer)
            self.perp_markets[market_index] = DataAndSlot(slot, decoded_data)

        return cb

    def _get_spot_market_callback(self, market_index: int):
        def cb(buffer: bytes, slot: int):
            if buffer is None:
                return

            decoded_data = self.program.coder.accounts.decode(buffer)
            self.spot_markets[market_index] = DataAndSlot(slot, decoded_data)

        return cb

    async def add_oracle(self, oracle: Pubkey, oracle_source: OracleSource):
        oracle_id = get_oracle_id(oracle, oracle_source)
        if oracle == Pubkey.default() or oracle_id in self.oracle:
            return True

        callback_id = self.bulk_account_loader.add_account(
            oracle, self._get_oracle_callback(oracle_id, oracle_source)
        )
        self.oracle_callbacks[oracle_id] = callback_id

        await self._wait_for_oracle(3, oracle_id)

        return True

    async def _wait_for_oracle(self, tries: int, oracle_id: str):
        while tries > 0:
            await asyncio.sleep(self.bulk_account_loader.frequency)
            if oracle_id in self.oracle:
                return
            tries -= 1
        print(
            f"WARNING: Oracle: {oracle_id} not found after {tries * self.bulk_account_loader.frequency} seconds, Location: {stack_trace()}"
        )

    def _get_oracle_callback(self, oracle_id: str, oracle_source: OracleSource):
        decode = get_oracle_decode_fn(oracle_source)

        def cb(buffer: bytes, slot: int):
            if buffer is None:
                return

            decoded_data = decode(buffer)
            self.oracle[oracle_id] = DataAndSlot(slot, decoded_data)

        return cb

    async def unsubscribe(self):
        for pubkey_str, callback_id in self.callbacks.items():
            self.bulk_account_loader.remove_account(
                Pubkey.from_string(pubkey_str), callback_id
            )

        for oracle_id, callback_id in self.oracle_callbacks.items():
            self.bulk_account_loader.remove_account(
                Pubkey.from_string(oracle_id.split("-")[0]), callback_id
            )

        self.callbacks.clear()
        self.oracle_callbacks.clear()

    def get_state_account_and_slot(self) -> Optional[DataAndSlot[StateAccount]]:
        return self.state

    def get_perp_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[PerpMarketAccount]]:
        return self.perp_markets.get(market_index)

    def get_spot_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[SpotMarketAccount]]:
        return self.spot_markets.get(market_index)

    def get_oracle_price_data_and_slot(
        self, oracle_id: str
    ) -> Optional[DataAndSlot[OraclePriceData]]:
        return self.oracle.get(oracle_id)

    def get_market_accounts_and_slots(self) -> list[DataAndSlot[PerpMarketAccount]]:
        return [
            DataAndSlot(account.slot, account.data)
            for account in self.perp_markets.values()
        ]

    def get_spot_market_accounts_and_slots(
        self,
    ) -> list[DataAndSlot[SpotMarketAccount]]:
        return [
            DataAndSlot(account.slot, account.data)
            for account in self.spot_markets.values()
        ]

    async def _set_perp_oracle_map(self):
        perp_markets = self.get_market_accounts_and_slots()
        for market in perp_markets:
            market_account = market.data
            market_index = market_account.market_index
            oracle = market_account.amm.oracle
            oracle_source = market_account.amm.oracle_source
            oracle_id = get_oracle_id(oracle, oracle_source)
            if oracle_id not in self.oracle:
                await self.add_oracle(oracle, oracle_source)
            self.perp_oracle_map[market_index] = oracle
            self.perp_oracle_strings_map[market_index] = oracle_id

    async def _set_spot_oracle_map(self):
        spot_markets = self.get_spot_market_accounts_and_slots()
        for market in spot_markets:
            market_account = market.data
            market_index = market_account.market_index
            oracle = market_account.oracle
            oracle_source = market_account.oracle_source
            oracle_id = get_oracle_id(oracle, oracle_source)
            if oracle_id not in self.oracle:
                await self.add_oracle(oracle, oracle_source)
            self.spot_oracle_map[market_index] = oracle
            self.spot_oracle_strings_map[market_index] = oracle_id

    def get_oracle_price_data_and_slot_for_perp_market(
        self, market_index: int
    ) -> Union[DataAndSlot[OraclePriceData], None]:
        perp_market_account = self.get_perp_market_and_slot(market_index)
        oracle = self.perp_oracle_map.get(market_index)
        oracle_id = self.perp_oracle_strings_map.get(market_index)

        if not perp_market_account or not oracle:
            return None

        if str(perp_market_account.data.amm.oracle) != str(oracle):
            asyncio.create_task(self._set_perp_oracle_map())

        return self.get_oracle_price_data_and_slot(oracle_id)

    def get_oracle_price_data_and_slot_for_spot_market(
        self, market_index: int
    ) -> Union[DataAndSlot[OraclePriceData], None]:
        spot_market_account = self.get_spot_market_and_slot(market_index)
        oracle = self.spot_oracle_map.get(market_index)
        oracle_id = self.spot_oracle_strings_map.get(market_index)

        if not spot_market_account or not oracle:
            return None

        if str(spot_market_account.data.oracle) != str(oracle):
            asyncio.create_task(self._set_spot_oracle_map())

        return self.get_oracle_price_data_and_slot(oracle_id)
