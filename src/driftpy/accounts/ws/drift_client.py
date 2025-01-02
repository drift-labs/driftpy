import asyncio
from typing import Optional, Sequence, Union

from anchorpy.program.core import Program
from solana.rpc.commitment import Commitment

from driftpy.accounts.oracle import get_oracle_decode_fn
from driftpy.accounts.types import (
    DataAndSlot,
    DriftClientAccountSubscriber,
    FullOracleWrapper,
)
from driftpy.accounts.ws.account_subscriber import WebsocketAccountSubscriber
from driftpy.addresses import (
    Pubkey,
    get_perp_market_public_key,
    get_spot_market_public_key,
    get_state_public_key,
)
from driftpy.constants.config import find_all_market_and_oracles
from driftpy.constants.perp_markets import mainnet_perp_market_configs
from driftpy.market_map.market_map import MarketMap
from driftpy.market_map.market_map_config import MarketMapConfig, WebsocketConfig
from driftpy.oracles.oracle_id import get_oracle_id
from driftpy.types import (
    MarketType,
    OracleInfo,
    OraclePriceData,
    PerpMarketAccount,
    SpotMarketAccount,
    StateAccount,
)


class WebsocketDriftClientAccountSubscriber(DriftClientAccountSubscriber):
    def __init__(
        self,
        program: Program,
        perp_market_indexes: Sequence[int],
        spot_market_indexes: Sequence[int],
        full_oracle_wrappers: Sequence[FullOracleWrapper],
        should_find_all_markets_and_oracles: bool,
        commitment: Commitment = Commitment("confirmed"),
    ):
        self.program = program
        self.commitment = commitment

        self.perp_market_indexes = perp_market_indexes
        self.spot_market_indexes = spot_market_indexes
        self.full_oracle_wrappers = full_oracle_wrappers
        self.should_find_all_markets_and_oracles = should_find_all_markets_and_oracles

        self.state_subscriber = None
        self.spot_market_subscribers = {}
        self.perp_market_subscribers = {}
        self.oracle_subscribers = {}
        self.spot_market_map = None
        self.perp_market_map = None
        self.spot_market_oracle_map: dict[int, Pubkey] = {}
        self.spot_market_oracle_strings_map: dict[int, str] = {}
        self.perp_market_oracle_map: dict[int, Pubkey] = {}
        self.perp_market_oracle_strings_map: dict[int, str] = {}

    async def subscribe(self):
        if self.is_subscribed():
            return

        state_public_key = get_state_public_key(self.program.program_id)
        self.state_subscriber = WebsocketAccountSubscriber[StateAccount](
            state_public_key, self.program, self.commitment
        )
        await self.state_subscriber.subscribe()

        if self.should_find_all_markets_and_oracles:
            (
                perp_ds,
                spot_ds,
                full_oracle_wrappers,
            ) = await find_all_market_and_oracles(self.program)

            self.perp_market_indexes = [
                data_and_slot.data.market_index for data_and_slot in perp_ds
            ]
            self.spot_market_indexes = [
                data_and_slot.data.market_index for data_and_slot in spot_ds
            ]
            self.full_oracle_wrappers = full_oracle_wrappers

            spot_market_config = MarketMapConfig(
                self.program,
                MarketType.Spot(),  # type: ignore
                WebsocketConfig(),
                self.program.provider.connection,
            )

            perp_market_config = MarketMapConfig(
                self.program,
                MarketType.Perp(),  # type: ignore
                WebsocketConfig(),
                self.program.provider.connection,
            )

            spot_market_map = MarketMap(spot_market_config)
            perp_market_map = MarketMap(perp_market_config)

            spot_market_map.init(spot_ds)
            perp_market_map.init(perp_ds)

            self.spot_market_map = spot_market_map
            self.perp_market_map = perp_market_map

            for full_oracle_wrapper in self.full_oracle_wrappers:
                await self.subscribe_to_oracle(full_oracle_wrapper)

            await spot_market_map.subscribe()
            await perp_market_map.subscribe()

        else:
            for market_index in self.perp_market_indexes:
                await self.subscribe_to_perp_market(market_index)

            for market_index in self.spot_market_indexes:
                await self.subscribe_to_spot_market(market_index)

            for full_oracle_wrapper in self.full_oracle_wrappers:
                await self.subscribe_to_oracle_info(full_oracle_wrapper)

        await self._set_perp_oracle_map()
        await self._set_spot_oracle_map()

    async def subscribe_to_spot_market(
        self,
        market_index: int,
        initial_data: Optional[DataAndSlot[SpotMarketAccount]] = None,
    ):
        if market_index in self.spot_market_subscribers:
            return

        spot_market_public_key = get_spot_market_public_key(
            self.program.program_id, market_index
        )
        spot_market_subscriber = WebsocketAccountSubscriber[SpotMarketAccount](
            spot_market_public_key,
            self.program,
            self.commitment,
            initial_data=initial_data,
        )
        await spot_market_subscriber.subscribe()
        self.spot_market_subscribers[market_index] = spot_market_subscriber

    async def subscribe_to_perp_market(
        self,
        market_index: int,
        initial_data: Optional[DataAndSlot[PerpMarketAccount]] = None,
    ):
        if market_index in self.perp_market_subscribers:
            return

        perp_market_public_key = get_perp_market_public_key(
            self.program.program_id, market_index
        )
        perp_market_subscriber = WebsocketAccountSubscriber[PerpMarketAccount](
            perp_market_public_key,
            self.program,
            self.commitment,
            initial_data=initial_data,
        )
        await perp_market_subscriber.subscribe()
        self.perp_market_subscribers[market_index] = perp_market_subscriber

    async def subscribe_to_oracle(self, full_oracle_wrapper: FullOracleWrapper):
        if full_oracle_wrapper.pubkey == Pubkey.default():
            return

        oracle_id = get_oracle_id(
            full_oracle_wrapper.pubkey,
            full_oracle_wrapper.oracle_source,
        )
        if oracle_id in self.oracle_subscribers:
            return

        oracle_subscriber = WebsocketAccountSubscriber[OraclePriceData](
            full_oracle_wrapper.pubkey,
            self.program,
            self.commitment,
            get_oracle_decode_fn(full_oracle_wrapper.oracle_source),
            initial_data=full_oracle_wrapper.oracle_price_data_and_slot,
        )
        await oracle_subscriber.subscribe()
        self.oracle_subscribers[oracle_id] = oracle_subscriber

    async def subscribe_to_oracle_info(
        self, oracle_info: OracleInfo | FullOracleWrapper
    ):
        source = None
        if isinstance(oracle_info, FullOracleWrapper):
            source = oracle_info.oracle_source
        else:
            source = oracle_info.source

        oracle_id = get_oracle_id(oracle_info.pubkey, source)
        if oracle_info.pubkey == Pubkey.default():
            return

        if oracle_id in self.oracle_subscribers:
            return

        oracle_subscriber = WebsocketAccountSubscriber[OraclePriceData](
            oracle_info.pubkey,
            self.program,
            self.commitment,
            get_oracle_decode_fn(source),
        )

        await oracle_subscriber.subscribe()
        self.oracle_subscribers[oracle_id] = oracle_subscriber

    def is_subscribed(self):
        return (
            self.state_subscriber is not None and self.state_subscriber.is_subscribed()
        )

    async def fetch(self):
        if not self.is_subscribed():
            return

        tasks = [self.state_subscriber.fetch()]

        for perp_market_subscriber in self.perp_market_subscribers.values():
            tasks.append(perp_market_subscriber.fetch())

        for spot_market_subscriber in self.spot_market_subscribers.values():
            tasks.append(spot_market_subscriber.fetch())

        for oracle_subscriber in self.oracle_subscribers.values():
            tasks.append(oracle_subscriber.fetch())

        await asyncio.gather(*tasks)

    async def add_oracle(self, oracle_info: OracleInfo):
        oracle_id = get_oracle_id(oracle_info.pubkey, oracle_info.source)
        if oracle_id in self.oracle_subscribers:
            return True

        if oracle_info.pubkey == Pubkey.default():
            return True

        return await self.subscribe_to_oracle_info(oracle_info)

    def get_state_account_and_slot(self) -> Optional[DataAndSlot[StateAccount]]:
        if not self.state_subscriber:
            raise ValueError("State subscriber not found")
        return self.state_subscriber.data_and_slot

    def get_perp_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[PerpMarketAccount]]:
        if self.perp_market_map:
            return self.perp_market_map.get(market_index)
        else:
            return self.perp_market_subscribers[market_index].data_and_slot

    def get_spot_market_and_slot(
        self, market_index: int
    ) -> Optional[DataAndSlot[SpotMarketAccount]]:
        if self.spot_market_map:
            return self.spot_market_map.get(market_index)
        else:
            return self.spot_market_subscribers[market_index].data_and_slot

    def get_oracle_price_data_and_slot(
        self, oracle_id: str
    ) -> Optional[DataAndSlot[OraclePriceData]]:
        return self.oracle_subscribers[oracle_id].data_and_slot

    async def unsubscribe(self):
        if self.is_subscribed():
            await self.state_subscriber.unsubscribe()
            if self.spot_market_map and self.perp_market_map:
                await self.spot_market_map.unsubscribe()
                await self.perp_market_map.unsubscribe()
            else:
                for spot_market_subscriber in self.spot_market_subscribers.values():
                    await spot_market_subscriber.unsubscribe()
                for perp_market_subscriber in self.perp_market_subscribers.values():
                    await perp_market_subscriber.unsubscribe()
            for oracle_subscriber in self.oracle_subscribers.values():
                await oracle_subscriber.unsubscribe()

    def get_market_accounts_and_slots(self) -> list[DataAndSlot[PerpMarketAccount]]:
        if self.perp_market_map:
            return [data_and_slot for data_and_slot in self.perp_market_map.values()]
        else:
            return [
                subscriber.data_and_slot
                for subscriber in self.perp_market_subscribers.values()
            ]

    def get_spot_market_accounts_and_slots(
        self,
    ) -> list[DataAndSlot[SpotMarketAccount]]:
        if self.spot_market_map:
            return [data_and_slot for data_and_slot in self.spot_market_map.values()]
        else:
            return [
                subscriber.data_and_slot
                for subscriber in self.spot_market_subscribers.values()
            ]

    async def _set_perp_oracle_map(self):
        perp_markets = self.get_market_accounts_and_slots()
        for market in perp_markets:
            if not market:
                continue

            perp_market_account = market.data
            market_index = perp_market_account.market_index
            oracle = perp_market_account.amm.oracle
            oracle_id = get_oracle_id(oracle, perp_market_account.amm.oracle_source)
            if oracle_id not in self.oracle_subscribers:
                await self.add_oracle(
                    OracleInfo(oracle, perp_market_account.amm.oracle_source)
                )
            self.perp_market_oracle_map[market_index] = oracle
            self.perp_market_oracle_strings_map[market_index] = oracle_id

    async def _set_spot_oracle_map(self):
        spot_markets = self.get_spot_market_accounts_and_slots()
        for market in spot_markets:
            if not market:
                continue

            spot_market_account = market.data
            market_index = spot_market_account.market_index
            oracle = spot_market_account.oracle
            oracle_id = get_oracle_id(oracle, spot_market_account.oracle_source)
            if oracle_id not in self.oracle_subscribers:
                await self.add_oracle(
                    OracleInfo(oracle, spot_market_account.oracle_source)
                )
            self.spot_market_oracle_map[market_index] = oracle
            self.spot_market_oracle_strings_map[market_index] = oracle_id

    def get_oracle_price_data_and_slot_for_perp_market(
        self, market_index: int
    ) -> Union[DataAndSlot[OraclePriceData], None]:
        perp_market_account = self.get_perp_market_and_slot(market_index)
        oracle = self.perp_market_oracle_map.get(market_index)
        oracle_id = self.perp_market_oracle_strings_map.get(market_index)

        if not perp_market_account:
            if any(
                market_index == market.market_index
                for market in mainnet_perp_market_configs
            ):
                raise ValueError(
                    f"No perp market account found for market index {market_index} but market should exist. This may be an issue with your RPC?"
                )

        if not oracle:
            print(f"No oracle found for market index {market_index}")

        if not perp_market_account or not oracle or not oracle_id:
            return None

        if perp_market_account.data.amm.oracle != oracle:
            asyncio.create_task(self._set_perp_oracle_map())

        return self.get_oracle_price_data_and_slot(oracle_id)

    def get_oracle_price_data_and_slot_for_spot_market(
        self, market_index: int
    ) -> Union[DataAndSlot[OraclePriceData], None]:
        spot_market_account = self.get_spot_market_and_slot(market_index)
        oracle = self.spot_market_oracle_map.get(market_index)
        oracle_id = self.spot_market_oracle_strings_map.get(market_index)

        if not spot_market_account or not oracle:
            return None

        if spot_market_account.data.oracle != oracle:
            asyncio.create_task(self._set_spot_oracle_map())

        return self.get_oracle_price_data_and_slot(oracle_id)
