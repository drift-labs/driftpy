import pickle
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

    async def pickle(self):
        await self.users.sync()
        self.users.dump()

        await self.user_stats.sync()
        self.user_stats.dump()

        await self.spot_markets.dump()
        await self.perp_markets.dump()

        await self.dump_oracles()

    async def unpickle(self):
        self.users.clear()
        self.user_stats.clear()
        self.spot_markets.clear()
        self.perp_markets.clear()

        await self.users.load()
        await self.user_stats.load()
        await self.spot_markets.load()
        await self.perp_markets.load()

        self.drift_client.resurrect(
            self.spot_markets, self.perp_markets, self.spot_oracles, self.perp_oracles
        )
        self.load_oracles()

    async def dump_oracles(self):
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

        self.last_oracle_slot = (await self.drift_client.connection.get_slot()).value

        with open(f"perporacles_{self.last_oracle_slot}.pkl", "wb") as f:
            pickle.dump(perp_oracles, f)

        with open(f"spotoracles_{self.last_oracle_slot}.pkl", "wb") as f:
            pickle.dump(spot_oracles, f)

    def load_oracles(self):
        with open(f"perporacles_{self.last_oracle_slot}.pkl", "rb") as f:
            perp_oracles: list[PickledData] = pickle.load(f)
            for oracle in perp_oracles:
                self.perp_oracles[oracle.pubkey] = oracle.data

        with open(f"spotoracles_{self.last_oracle_slot}.pkl", "rb") as f:
            spot_oracles: list[PickledData] = pickle.load(f)
            for oracle in spot_oracles:
                self.spot_oracles[oracle.pubkey] = oracle.data
