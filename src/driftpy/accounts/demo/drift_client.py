from typing import Optional

from anchorpy import Program
from solana.rpc.commitment import Commitment
from solders.pubkey import Pubkey

from driftpy.accounts import get_state_account_and_slot
from driftpy.accounts.get_accounts import (
    get_perp_market_account_and_slot,
    get_spot_market_account_and_slot,
)
from driftpy.accounts.oracle import oracle_ai_to_oracle_price_data
from driftpy.accounts.types import DataAndSlot, DriftClientAccountSubscriber
from driftpy.oracles.oracle_id import get_oracle_id
from driftpy.types import (
    OraclePriceData,
    PerpMarketAccount,
    SpotMarketAccount,
    StateAccount,
)


class DemoDriftClientAccountSubscriber(DriftClientAccountSubscriber):
    def __init__(
        self,
        program: Program,
        perp_market_indexes,
        spot_market_indexes,
        oracle_infos,
        commitment: Commitment = "confirmed",
    ):
        self.program = program
        self.perp_market_indexes = perp_market_indexes
        self.spot_market_indexes = spot_market_indexes
        self.oracle_infos = oracle_infos
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

        spot_market_indexes = sorted(self.spot_market_indexes)
        perp_market_indexes = sorted(self.perp_market_indexes)

        for index in spot_market_indexes:
            spot_market_and_slot = await get_spot_market_account_and_slot(
                self.program, index
            )
            spot_markets.append(spot_market_and_slot)

        for index in perp_market_indexes:
            perp_market_and_slot = await get_perp_market_account_and_slot(
                self.program, index
            )
            perp_markets.append(perp_market_and_slot)

        oracle_pubkeys = [oracle.pubkey for oracle in self.oracle_infos]
        oracle_accounts = await self.program.provider.connection.get_multiple_accounts(
            oracle_pubkeys
        )
        print("ORACLE ACCOUNTS", oracle_accounts)

        for i, oracle_ai in enumerate(oracle_accounts.value):
            if oracle_ai.owner == Pubkey.from_string(
                "NativeLoader1111111111111111111111111111111"
            ):
                continue
            oracle_price_data_and_slot = oracle_ai_to_oracle_price_data(
                oracle_ai, self.oracle_infos[i].source
            )
            oracle_id = get_oracle_id(
                self.oracle_infos[i].pubkey, self.oracle_infos[i].source
            )
            oracle_data[oracle_id] = oracle_price_data_and_slot

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
        self, oracle_id: str
    ) -> Optional[DataAndSlot[OraclePriceData]]:
        return self.cache["oracle_price_data"][oracle_id]

    async def unsubscribe(self):
        self.cache = None

    def get_market_accounts_and_slots(self) -> list[DataAndSlot[PerpMarketAccount]]:
        return self.cache["perp_markets"]

    def get_spot_market_accounts_and_slots(
        self,
    ) -> list[DataAndSlot[SpotMarketAccount]]:
        return self.cache["spot_markets"]
