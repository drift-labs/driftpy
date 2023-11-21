import asyncio
from dataclasses import dataclass
from typing import Mapping, Callable, Optional, TypeVar

from driftpy.accounts import DriftClientAccountSubscriber, DataAndSlot

from anchorpy import Program
from solders.pubkey import Pubkey

from driftpy.accounts.bulk_account_loader import BulkAccountLoader
from driftpy.accounts.oracle import get_oracle_decode_fn
from driftpy.addresses import get_state_public_key
from driftpy.types import PerpMarket, SpotMarket, OraclePriceData, State, OracleSource


class PollingDriftClientAccountSubscriber(DriftClientAccountSubscriber):
    def __init__(
        self,
        program: Program,
        bulk_account_loader: BulkAccountLoader,
    ):
        self.bulk_account_loader = bulk_account_loader
        self.program = program
        self.is_subscribed = False
        self.callbacks: dict[str, int] = {}

        self.state: Optional[DataAndSlot[State]] = None
        self.perp_markets = {}
        self.spot_markets = {}
        self.oracle = {}

    async def subscribe(self):
        await self.update_accounts_to_poll()

        while self.state is None:
            await asyncio.sleep(0.5)

    async def update_accounts_to_poll(self):
        state_public_key = get_state_public_key(self.program.program_id)
        state_callback_id = self.bulk_account_loader.add_account(
            state_public_key, self._get_state_callback()
        )
        self.callbacks[str(state_public_key)] = state_callback_id

        perp_markets = await self.program.account["PerpMarket"].all()
        for perp_market in perp_markets:
            pubkey = perp_market.public_key
            market_index = perp_market.account.market_index
            callback_id = self.bulk_account_loader.add_account(
                pubkey, self._get_perp_market_callback(market_index)
            )
            self.callbacks[str(pubkey)] = callback_id
            self.add_oracle(
                perp_market.account.amm.oracle, perp_market.account.amm.oracle_source
            )

        spot_markets = await self.program.account["SpotMarket"].all()
        for spot_market in spot_markets:
            pubkey = spot_market.public_key
            market_index = spot_market.account.market_index
            callback_id = self.bulk_account_loader.add_account(
                pubkey, self._get_spot_market_callback(market_index)
            )
            self.callbacks[str(pubkey)] = callback_id
            self.add_oracle(
                spot_market.account.oracle, spot_market.account.oracle_source
            )

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

    async def get_state_account_and_slot(self) -> Optional[DataAndSlot[State]]:
        return self.state

    async def get_perp_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[PerpMarket]]:
        return self.perp_markets.get(market_index)

    async def get_spot_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[SpotMarket]]:
        return self.spot_markets.get(market_index)

    async def get_oracle_price_data_and_slot(
        self, oracle: Pubkey
    ) -> Optional[DataAndSlot[OraclePriceData]]:
        return self.oracle.get(str(oracle))
