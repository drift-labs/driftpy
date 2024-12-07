import asyncio
import pickle
import os
from typing import Optional
from driftpy.drift_client import DriftClient
from driftpy.market_map.market_map import MarketMap
from driftpy.types import PickledData
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.userstats_map import UserStatsMap


# generally this is not intended for use with websocket drift client subscriber
class Vat:
    def __init__(
        self,
        drift_client: DriftClient,
        users: UserMap,
        user_stats: UserStatsMap,
        spot_markets: MarketMap,
        perp_markets: MarketMap,
    ):
        self.drift_client = drift_client
        self.users = users
        self.user_stats = user_stats
        self.spot_markets = spot_markets
        self.perp_markets = perp_markets
        self.last_oracle_slot = 0
        self.perp_oracles = {}
        self.spot_oracles = {}

    async def pickle(self, file_prefix: Optional[str] = None) -> dict[str, str]:
        users_sync = asyncio.create_task(self.users.sync())
        user_stats_sync = asyncio.create_task(self.user_stats.sync())
        spot_markets_pre_dump = asyncio.create_task(self.spot_markets.pre_dump())
        perp_markets_pre_dump = asyncio.create_task(self.perp_markets.pre_dump())
        register_oracle_slot = asyncio.create_task(self.register_oracle_slot())

        await asyncio.gather(
            users_sync,
            user_stats_sync,
            spot_markets_pre_dump,
            perp_markets_pre_dump,
            register_oracle_slot,
        )

        spot_market_raw = spot_markets_pre_dump.result()
        perp_market_raw = perp_markets_pre_dump.result()

        filenames = self.get_filenames(file_prefix)

        self.users.dump(filenames["users"])

        self.user_stats.dump(filenames["userstats"])

        self.spot_markets.dump(spot_market_raw, filenames["spot_markets"])

        self.perp_markets.dump(perp_market_raw, filenames["perp_markets"])

        self.dump_oracles(filenames["spot_oracles"], filenames["perp_oracles"])

        return filenames

    async def unpickle(
        self,
        users_filename: Optional[str] = None,
        user_stats_filename: Optional[str] = None,
        spot_markets_filename: Optional[str] = None,
        perp_markets_filename: Optional[str] = None,
        spot_oracles_filename: Optional[str] = None,
        perp_oracles_filename: Optional[str] = None,
    ):
        self.users.clear()
        self.user_stats.clear()
        self.spot_markets.clear()
        self.perp_markets.clear()

        await self.users.load(users_filename)
        await self.user_stats.load(user_stats_filename)
        await self.spot_markets.load(spot_markets_filename)
        await self.perp_markets.load(perp_markets_filename)

        self.load_oracles(spot_oracles_filename, perp_oracles_filename)

        self.drift_client.resurrect(
            self.spot_markets, self.perp_markets, self.spot_oracles, self.perp_oracles
        )

    async def register_oracle_slot(self):
        self.last_oracle_slot = (await self.drift_client.connection.get_slot()).value

    def dump_oracles(
        self, spot_filepath: Optional[str] = None, perp_filepath: Optional[str] = None
    ):
        perp_oracles = []
        for market in self.drift_client.get_perp_market_accounts():
            oracle_price_data = self.drift_client.get_oracle_price_data_for_perp_market(
                market.market_index
            )
            perp_oracles.append(
                PickledData(pubkey=market.market_index, data=oracle_price_data)
            )

        spot_oracles = []
        for market in self.drift_client.get_spot_market_accounts():
            oracle_price_data = self.drift_client.get_oracle_price_data_for_spot_market(
                market.market_index
            )
            spot_oracles.append(
                PickledData(pubkey=market.market_index, data=oracle_price_data)
            )

        perp_path = perp_filepath or f"perporacles_{self.last_oracle_slot}.pkl"
        with open(perp_path, "wb") as f:
            pickle.dump(perp_oracles, f)

        spot_path = spot_filepath or f"spotoracles_{self.last_oracle_slot}.pkl"
        with open(spot_path, "wb") as f:
            pickle.dump(spot_oracles, f)

    def load_oracles(
        self, spot_filename: Optional[str] = None, perp_filename: Optional[str] = None
    ):
        if perp_filename is None:
            perp_filename = f"perporacles_{self.last_oracle_slot}.pkl"
        if spot_filename is None:
            spot_filename = f"spotoracles_{self.last_oracle_slot}.pkl"

        if os.path.exists(perp_filename):
            with open(perp_filename, "rb") as f:
                perp_oracles: list[PickledData] = pickle.load(f)
                for oracle in perp_oracles:
                    self.perp_oracles[oracle.pubkey] = (
                        oracle.data
                    )  # oracle.pubkey is actually a market index
        else:
            raise FileNotFoundError(f"File {perp_filename} not found")

        if os.path.exists(spot_filename):
            with open(spot_filename, "rb") as f:
                spot_oracles: list[PickledData] = pickle.load(f)
                for oracle in spot_oracles:
                    self.spot_oracles[oracle.pubkey] = (
                        oracle.data
                    )  # oracle.pubkey is actually a market index
        else:
            raise FileNotFoundError(f"File {spot_filename} not found")

    def get_filenames(self, prefix: Optional[str]) -> dict[str, str]:
        filenames = {}

        usermap_slot = self.users.get_slot()
        userstats_slot = self.user_stats.latest_slot
        spot_markets_slot = self.spot_markets.latest_slot
        perp_markets_slot = self.perp_markets.latest_slot
        oracle_slot = self.last_oracle_slot

        if prefix:
            filenames["users"] = f"{prefix}usermap_{usermap_slot}.pkl"
            filenames["userstats"] = f"{prefix}userstats_{userstats_slot}.pkl"
            filenames["spot_markets"] = f"{prefix}spot_{spot_markets_slot}.pkl"
            filenames["perp_markets"] = f"{prefix}perp_{perp_markets_slot}.pkl"
            filenames["spot_oracles"] = f"{prefix}spotoracles_{oracle_slot}.pkl"
            filenames["perp_oracles"] = f"{prefix}perporacles_{oracle_slot}.pkl"
        else:
            filenames["users"] = f"usermap_{usermap_slot}.pkl"
            filenames["userstats"] = f"userstats_{userstats_slot}.pkl"
            filenames["spot_markets"] = f"spot_{spot_markets_slot}.pkl"
            filenames["perp_markets"] = f"perp_{perp_markets_slot}.pkl"
            filenames["spot_oracles"] = f"spotoracles_{oracle_slot}.pkl"
            filenames["perp_oracles"] = f"perporacles_{oracle_slot}.pkl"

        return filenames
