import asyncio
import os
from asyncio import create_task, gather
from datetime import datetime
from typing import Optional

from anchorpy.provider import Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.drift_client import DriftClient
from driftpy.market_map.market_map import MarketMap
from driftpy.market_map.market_map_config import MarketMapConfig
from driftpy.market_map.market_map_config import (
    WebsocketConfig as MarketMapWebsocketConfig,
)
from driftpy.pickle.vat import Vat
from driftpy.types import MarketType
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import UserMapConfig, UserStatsMapConfig
from driftpy.user_map.user_map_config import (
    WebsocketConfig as UserMapWebsocketConfig,
)
from driftpy.user_map.userstats_map import UserStatsMap

load_dotenv()


def load_newest_files(directory: Optional[str] = None) -> dict[str, str]:
    directory = directory or os.getcwd()
    print(f"Loading newest files from {directory}")

    newest_files: dict[str, tuple[str, int]] = {}

    prefixes = ["perp", "perporacles", "spot", "spotoracles", "usermap", "userstats"]

    for filename in os.listdir(directory):
        if filename.endswith(".pkl") and any(
            filename.startswith(prefix + "_") for prefix in prefixes
        ):
            print(f"Found pickle file: {filename}")
            start = filename.rindex("_") + 1  # Use rindex to find the last underscore
            prefix = filename[: start - 1]
            end = filename.index(".")
            slot = int(filename[start:end])
            if prefix not in newest_files or slot > newest_files[prefix][1]:
                newest_files[prefix] = (directory + "/" + filename, slot)

    # mapping e.g { 'spotoracles' : 'spotoracles_272636137.pkl' }
    prefix_to_filename = {
        prefix: filename for prefix, (filename, _) in newest_files.items()
    }

    return prefix_to_filename


class BackendState:
    connection: AsyncClient
    dc: DriftClient
    spot_map: MarketMap
    perp_map: MarketMap
    user_map: UserMap
    stats_map: UserStatsMap

    current_pickle_path: str
    last_oracle_slot: int
    vat: Vat
    ready: bool

    def initialize(
        self, url: str
    ):  # Not using __init__ because we need the rpc url to be passed in
        print(f"Initializing backend with RPC URL: {url}")
        self.connection = AsyncClient(url)
        self.dc = DriftClient(
            self.connection,
            Wallet.dummy(),
            "mainnet",
            account_subscription=AccountSubscriptionConfig("cached"),
        )
        self.perp_map = MarketMap(
            MarketMapConfig(
                self.dc.program,
                MarketType.Perp(),
                MarketMapWebsocketConfig(),
                self.dc.connection,
            )
        )
        self.spot_map = MarketMap(
            MarketMapConfig(
                self.dc.program,
                MarketType.Spot(),
                MarketMapWebsocketConfig(),
                self.dc.connection,
            )
        )
        self.user_map = UserMap(UserMapConfig(self.dc, UserMapWebsocketConfig()))
        self.stats_map = UserStatsMap(UserStatsMapConfig(self.dc))
        self.vat = Vat(
            self.dc,
            self.user_map,
            self.stats_map,
            self.spot_map,
            self.perp_map,
        )
        self.ready = False
        self.current_pickle_path = "bootstrap"
        print("Backend initialization complete")

    async def bootstrap(self):
        print("Starting bootstrap process...")
        await self.dc.subscribe()
        await gather(
            create_task(self.spot_map.subscribe()),
            create_task(self.perp_map.subscribe()),
            create_task(self.user_map.subscribe()),
            create_task(self.stats_map.subscribe()),
        )
        self.current_pickle_path = "bootstrap"
        print("Bootstrap complete")

    async def take_pickle_snapshot(self):
        now = datetime.now()
        folder_name = now.strftime("vat-%Y-%m-%d-%H-%M-%S")
        if not os.path.exists("pickles"):
            os.makedirs("pickles")
        path = os.path.join("pickles", folder_name, "")
        print(f"Taking pickle snapshot in {path}")

        os.makedirs(path, exist_ok=True)
        result = await self.vat.pickle(path)
        # await self.load_pickle_snapshot(path)
        print("Pickle snapshot complete")
        return result, path

    async def load_pickle_snapshot(self, directory: str):
        print(f"Loading pickle snapshot from {directory}")
        pickle_map = load_newest_files(directory)
        print(pickle_map)
        self.current_pickle_path = os.path.realpath(directory)
        await self.vat.unpickle(
            users_filename=pickle_map["usermap"],
            user_stats_filename=pickle_map["userstats"],
            spot_markets_filename=pickle_map["spot"],
            perp_markets_filename=pickle_map["perp"],
            spot_oracles_filename=pickle_map["spotoracles"],
            perp_oracles_filename=pickle_map["perporacles"],
        )

        self.last_oracle_slot = int(
            pickle_map["perporacles"].split("_")[-1].split(".")[0]
        )
        print(f"Loaded pickle snapshot with last oracle slot: {self.last_oracle_slot}")
        return pickle_map

    async def close(self):
        print("Closing backend connections...")
        await self.dc.unsubscribe()
        await self.connection.close()
        print("Backend closed")


async def main():
    backend = BackendState()
    backend.initialize(os.environ.get("MAINNET_RPC_ENDPOINT") or "")
    await backend.bootstrap()
    content, path = await backend.take_pickle_snapshot()
    print(content)
    print(path)
    await backend.load_pickle_snapshot(path)
    # await backend.take_pickle_snapshot()


if __name__ == "__main__":
    asyncio.run(main())
