import asyncio
from typing import Optional, Union, cast

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
from driftpy.events.event_subscriber import EventEmitter
from driftpy.oracles.oracle_id import get_num_to_source, get_oracle_id
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
        perp_market_indexes: list[int],
        spot_market_indexes: list[int],
        oracle_infos: list[OracleInfo],
        should_find_all_markets_and_oracles: bool,
    ):
        self.bulk_account_loader = bulk_account_loader
        self.program = program
        self.is_subscribed = False
        self.callbacks: dict[str, int] = {}

        self.perp_market_indexes = perp_market_indexes
        self.spot_market_indexes = spot_market_indexes
        self.oracle_infos: list[OracleInfo] = oracle_infos
        self.should_find_all_markets_and_oracles = should_find_all_markets_and_oracles

        self.state: Optional[DataAndSlot[StateAccount]] = None
        self.perp_markets: dict[int, DataAndSlot[PerpMarketAccount]] = {}
        self.spot_markets: dict[int, DataAndSlot[SpotMarketAccount]] = {}
        self.oracle: dict[str, DataAndSlot[OraclePriceData]] = {}
        self.perp_oracle_map: dict[int, Pubkey] = {}
        self.spot_oracle_map: dict[int, Pubkey] = {}
        self.spot_oracle_string_map: dict[int, str] = {}
        self.perp_oracle_string_map: dict[int, str] = {}

        self.is_subscribing = False
        self.subscription_promise: Optional[asyncio.Future[bool]] = None
        self.event_emitter = EventEmitter()

    async def subscribe(self):
        if len(self.callbacks) != 0:
            return

        if self.is_subscribed:
            return True

        if self.is_subscribing and self.subscription_promise is not None:
            return await self.subscription_promise

        self.is_subscribing = True
        self.subscription_promise = asyncio.Future()

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

        subscription_succeeded = False
        retries = 0
        while not subscription_succeeded and retries < 5:
            await self.fetch()
            subscription_succeeded = self.accounts_ready()
            retries += 1

        if subscription_succeeded:
            self.event_emitter.emit("update")

        if not subscription_succeeded:
            print("Failed to subscribe")

        await asyncio.gather(
            self._set_perp_oracle_map(),
            self._set_spot_oracle_map(),
        )

        self.is_subscribing = False
        self.is_subscribed = subscription_succeeded
        self.subscription_promise.set_result(subscription_succeeded)

    async def fetch(self):
        await self.bulk_account_loader.load()

        # Process program accounts
        for pubkey_str, callback_id in self.callbacks.items():
            if "-" in pubkey_str:
                pubkey_str = pubkey_str.split("-")[0]

            pubkey = Pubkey.from_string(pubkey_str)
            buffer_and_slot = self.bulk_account_loader.get_buffer_and_slot(pubkey)

            if not buffer_and_slot:
                continue

            buffer = buffer_and_slot.buffer
            slot = buffer_and_slot.slot

            if buffer:
                if pubkey_str in self.perp_markets:
                    market_index = next(
                        k
                        for k, v in self.perp_markets.items()
                        if str(v.data.pubkey) == pubkey_str
                    )
                    decoded_data = self.program.coder.accounts.decode(buffer)
                    self.perp_markets[market_index] = cast(
                        DataAndSlot[PerpMarketAccount],
                        DataAndSlot(slot, decoded_data),
                    )

                elif pubkey_str in self.spot_markets:
                    market_index = next(
                        k
                        for k, v in self.spot_markets.items()
                        if str(v.data.pubkey) == pubkey_str
                    )
                    decoded_data = self.program.coder.accounts.decode(buffer)
                    self.spot_markets[market_index] = cast(
                        DataAndSlot[SpotMarketAccount],
                        DataAndSlot(slot, decoded_data),
                    )

                elif pubkey == get_state_public_key(self.program.program_id):
                    decoded_data = self.program.coder.accounts.decode(buffer)
                    self.state = cast(
                        DataAndSlot[StateAccount],
                        DataAndSlot(slot, decoded_data),
                    )

        for oracle_id, oracle_info in self.oracle.items():
            pubkey, source_num = oracle_id.split("-")
            pubkey = Pubkey.from_string(pubkey)
            source_num = int(source_num)

            oracle_source = get_num_to_source(source_num)
            buffer_and_slot = self.bulk_account_loader.get_buffer_and_slot(pubkey)

            if not buffer_and_slot:
                continue

            buffer = buffer_and_slot.buffer
            slot = buffer_and_slot.slot

            if buffer:
                decode = get_oracle_decode_fn(oracle_source)
                oracle_price_data = decode(buffer)
                self.oracle[oracle_id] = DataAndSlot(slot, oracle_price_data)

    def accounts_ready(self) -> bool:
        return self.state is not None

    async def update_accounts_to_poll(self):
        state_public_key = get_state_public_key(self.program.program_id)
        state_callback_id = await self.bulk_account_loader.add_account(
            state_public_key, self._get_state_callback()
        )
        self.callbacks[str(state_public_key)] = state_callback_id

        for perp_market_index in self.perp_market_indexes:
            pubkey = get_perp_market_public_key(
                self.program.program_id, perp_market_index
            )
            callback_id = await self.bulk_account_loader.add_account(
                pubkey, self._get_perp_market_callback(perp_market_index)
            )
            self.callbacks[str(pubkey)] = callback_id

        for spot_market_index in self.spot_market_indexes:
            pubkey = get_spot_market_public_key(
                self.program.program_id, spot_market_index
            )
            callback_id = await self.bulk_account_loader.add_account(
                pubkey, self._get_spot_market_callback(spot_market_index)
            )
            self.callbacks[str(pubkey)] = callback_id

        for oracle_info in self.oracle_infos:
            if not isinstance(oracle_info, OracleInfo):
                raise ValueError(f"Invalid oracle info type: {type(oracle_info)}")

            await self.add_oracle(oracle_info.pubkey, oracle_info.source)

    def _get_state_callback(self):
        def cb(buffer: bytes, slot: int):
            if buffer is None:
                return

            decoded_data = self.program.coder.accounts.decode(buffer)
            self.state = cast(
                DataAndSlot[StateAccount],
                DataAndSlot(slot, decoded_data),
            )

        return cb

    def _get_perp_market_callback(self, market_index: int):
        def cb(buffer: bytes, slot: int):
            if buffer is None:
                return

            decoded_data = self.program.coder.accounts.decode(buffer)
            self.perp_markets[market_index] = cast(
                DataAndSlot[PerpMarketAccount],
                DataAndSlot(slot, decoded_data),
            )

        return cb

    def _get_spot_market_callback(self, market_index: int):
        def cb(buffer: bytes, slot: int):
            if buffer is None:
                return

            decoded_data = self.program.coder.accounts.decode(buffer)
            self.spot_markets[market_index] = cast(
                DataAndSlot[SpotMarketAccount],
                DataAndSlot(slot, decoded_data),
            )

        return cb

    async def add_oracle(self, oracle: Pubkey, oracle_source: OracleSource):
        oracle_id = get_oracle_id(oracle, oracle_source)
        if oracle == Pubkey.default() or oracle_id in self.oracle:
            return True

        if oracle_id in self.callbacks:
            return True

        callback_id = await self.bulk_account_loader.add_account(
            oracle,
            self._get_oracle_callback(oracle_id, oracle_source),
        )
        self.callbacks[oracle_id] = callback_id

        await self._wait_for_oracle(2, oracle_id)

        return True

    async def _wait_for_oracle(self, tries: int, oracle: str):
        for _ in range(tries):
            if oracle in self.bulk_account_loader.buffer_and_slot_map:
                return
            await asyncio.sleep(self.bulk_account_loader.frequency)

        print(
            f"WARNING: Oracle: {oracle} not found after {tries * self.bulk_account_loader.frequency} seconds, Location: {stack_trace()}"
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
            self.spot_oracle_string_map[market_index] = oracle_id

    def get_oracle_price_data_and_slot_for_perp_market(
        self, market_index: int
    ) -> Union[DataAndSlot[OraclePriceData], None]:
        perp_market_account = self.get_perp_market_and_slot(market_index)
        oracle = self.perp_oracle_map.get(market_index)

        if not perp_market_account or not oracle:
            return None

        if str(perp_market_account.data.amm.oracle) != str(oracle):
            asyncio.create_task(self._set_perp_oracle_map())

        oracle_id = get_oracle_id(oracle, perp_market_account.data.amm.oracle_source)
        return self.get_oracle_price_data_and_slot(oracle_id)

    def get_oracle_price_data_and_slot_for_spot_market(
        self, market_index: int
    ) -> Union[DataAndSlot[OraclePriceData], None]:
        spot_market_account = self.get_spot_market_and_slot(market_index)
        print("map", self.spot_oracle_map)
        oracle = self.spot_oracle_map.get(market_index)
        oracle_id = self.spot_oracle_string_map.get(market_index)

        if not spot_market_account or not oracle_id:
            return None

        if str(spot_market_account.data.oracle) != str(oracle):
            asyncio.create_task(self._set_spot_oracle_map())

        return self.get_oracle_price_data_and_slot(oracle_id)
