from typing import Optional, Sequence

from driftpy.accounts import DriftClientAccountSubscriber, DataAndSlot

from anchorpy import Program
from solders.pubkey import Pubkey

from driftpy.accounts.bulk_account_loader import BulkAccountLoader
from driftpy.accounts.oracle import get_oracle_decode_fn
from driftpy.addresses import (
    get_state_public_key,
    get_perp_market_public_key,
    get_spot_market_public_key,
)
from driftpy.constants.config import find_all_market_and_oracles
from driftpy.types import (
    PerpMarketAccount,
    SpotMarketAccount,
    OraclePriceData,
    StateAccount,
    OracleSource,
    OracleInfo,
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

        self.perp_market_indexes = perp_market_indexes
        self.spot_market_indexes = spot_market_indexes
        self.oracle_infos = oracle_infos
        self.should_find_all_markets_and_oracles = should_find_all_markets_and_oracles

        self.state: Optional[DataAndSlot[StateAccount]] = None
        self.perp_markets = {}
        self.spot_markets = {}
        self.oracle = {}

    async def subscribe(self):
        if len(self.callbacks) != 0:
            return

        if self.should_find_all_markets_and_oracles:
            (
                perp_market_indexes,
                spot_market_indexes,
                oracle_infos,
            ) = await find_all_market_and_oracles(self.program)
            self.perp_market_indexes = perp_market_indexes
            self.spot_market_indexes = spot_market_indexes
            self.oracle_infos = oracle_infos

        await self.update_accounts_to_poll()

        while self.accounts_ready() is False:
            await self.bulk_account_loader.load()

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
            self.add_oracle(oracle_info.pubkey, oracle_info.source)

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

    def add_oracle(self, oracle: Pubkey, oracle_source: OracleSource):
        if oracle == Pubkey.default():
            return

        oracle_str = str(oracle)
        if oracle_str in self.callbacks:
            return

        callback_id = self.bulk_account_loader.add_account(
            oracle, self._get_oracle_callback(oracle_str, oracle_source)
        )
        self.callbacks[oracle_str] = callback_id

    def _get_oracle_callback(self, oracle_str: str, oracle_source: OracleSource):
        decode = get_oracle_decode_fn(oracle_source)

        def cb(buffer: bytes, slot: int):
            if buffer is None:
                return

            decoded_data = decode(buffer)
            self.oracle[oracle_str] = DataAndSlot(slot, decoded_data)

        return cb

    def unsubscribe(self):
        for pubkey_str, callback_id in self.callbacks.items():
            self.bulk_account_loader.remove_account(
                Pubkey.from_string(pubkey_str), callback_id
            )
        self.callbacks.clear()

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
        self, oracle: Pubkey
    ) -> Optional[DataAndSlot[OraclePriceData]]:
        return self.oracle.get(str(oracle))

    def get_market_accounts_and_slots(self) -> list[DataAndSlot[PerpMarketAccount]]:
        return [self.perp_markets.values()]

    def get_spot_market_accounts_and_slots(
        self,
    ) -> list[DataAndSlot[SpotMarketAccount]]:
        return [self.spot_markets.values()]
