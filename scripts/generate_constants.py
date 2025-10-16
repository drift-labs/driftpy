import argparse
import asyncio
import os
from pathlib import Path

import dotenv
from anchorpy import Wallet
from solana.rpc.async_api import AsyncClient

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.constants.perp_markets import PerpMarketConfig
from driftpy.constants.spot_markets import SpotMarketConfig
from driftpy.drift_client import DriftClient

dotenv.load_dotenv()

PERP_MARKET_PREAMBLE = """from dataclasses import dataclass

from solders.pubkey import Pubkey

from driftpy.types import OracleSource


@dataclass
class PerpMarketConfig:
    symbol: str
    base_asset_symbol: str
    market_index: int
    oracle: Pubkey
    oracle_source: OracleSource

"""


SPOT_MARKET_PREAMBLE = """from dataclasses import dataclass
from typing import Optional

from solders.pubkey import Pubkey

from driftpy.types import OracleSource


@dataclass
class SpotMarketConfig:
    symbol: str
    market_index: int
    oracle: Pubkey
    oracle_source: OracleSource
    mint: Pubkey
    decimals: Optional[int] = None


WRAPPED_SOL_MINT = Pubkey.from_string("So11111111111111111111111111111111111111112")

"""


def decode_name(name) -> str:
    return bytes(name).decode("utf-8").strip()


async def generate_spot_configs(drift_client: DriftClient, env: str) -> str:
    spot_markets = sorted(
        drift_client.get_spot_market_accounts(), key=lambda market: market.market_index
    )

    configs = []
    for market in spot_markets:
        config = SpotMarketConfig(
            symbol=decode_name(market.name),
            market_index=market.market_index,
            oracle=market.oracle,
            oracle_source=market.oracle_source,
            mint=market.mint,
            decimals=market.decimals,
        )
        configs.append(config)

    output = f"""
{env}_spot_market_configs: list[SpotMarketConfig] = ["""

    for config in configs:
        output += f"""
    SpotMarketConfig(
        symbol="{config.symbol}",
        market_index={config.market_index},
        oracle=Pubkey.from_string("{str(config.oracle)}"),
        oracle_source=OracleSource.{config.oracle_source.__class__.__name__}(),  # type: ignore
        mint=Pubkey.from_string("{str(config.mint)}"),
        decimals={config.decimals},
    ),"""

    output += "\n]\n"
    return output


async def generate_full_spot_configs(
    drift_client: DriftClient, dev_drift_client: DriftClient
) -> str:
    print("Generating full spot configs")
    mainnet_spot_markets = sorted(
        drift_client.get_spot_market_accounts(), key=lambda market: market.market_index
    )

    print("Generating devnet spot configs")
    devnet_spot_markets = sorted(
        dev_drift_client.get_spot_market_accounts(),
        key=lambda market: market.market_index,
    )

    print("Generating configs")
    devnet_configs = []
    mainnet_configs = []
    for market in devnet_spot_markets:
        config = SpotMarketConfig(
            symbol=decode_name(market.name),
            market_index=market.market_index,
            oracle=market.oracle,
            oracle_source=market.oracle_source,
            mint=market.mint,
            decimals=market.decimals,
        )
        devnet_configs.append(config)

    for market in mainnet_spot_markets:
        config = SpotMarketConfig(
            symbol=decode_name(market.name),
            market_index=market.market_index,
            oracle=market.oracle,
            oracle_source=market.oracle_source,
            mint=market.mint,
            decimals=market.decimals,
        )
        mainnet_configs.append(config)

    output = SPOT_MARKET_PREAMBLE + "\n"
    output += """
devnet_spot_market_configs: list[SpotMarketConfig] = ["""

    for config in devnet_configs:
        output += f"""
    SpotMarketConfig(
        symbol="{config.symbol}",
        market_index={config.market_index},
        oracle=Pubkey.from_string("{str(config.oracle)}"),
        oracle_source=OracleSource.{config.oracle_source.__class__.__name__}(),  # type: ignore
        mint=Pubkey.from_string("{str(config.mint)}"),
        decimals={config.decimals},
    ),"""

    output += "\n]\n"

    output += """
mainnet_spot_market_configs: list[SpotMarketConfig] = ["""

    for config in mainnet_configs:
        output += f"""
    SpotMarketConfig(
        symbol="{config.symbol}",
        market_index={config.market_index},
        oracle=Pubkey.from_string("{str(config.oracle)}"),
        oracle_source=OracleSource.{config.oracle_source.__class__.__name__}(),  # type: ignore
        mint=Pubkey.from_string("{str(config.mint)}"),
        decimals={config.decimals},
    ),"""

    output += "\n]\n"
    return output


async def generate_full_perp_configs(
    drift_client: DriftClient, dev_drift_client: DriftClient
) -> str:
    print("Generating full perp configs")
    mainnet_perp_markets = sorted(
        drift_client.get_perp_market_accounts(), key=lambda market: market.market_index
    )

    print("Generating devnet perp configs")
    devnet_perp_markets = sorted(
        dev_drift_client.get_perp_market_accounts(),
        key=lambda market: market.market_index,
    )
    print("Generating configs")
    devnet_configs = []
    mainnet_configs = []
    for market in devnet_perp_markets:
        config = PerpMarketConfig(
            symbol=decode_name(market.name),
            base_asset_symbol="-".join(decode_name(market.name).split("-")[:-1]),
            market_index=market.market_index,
            oracle=market.amm.oracle,
            oracle_source=market.amm.oracle_source,
        )
        devnet_configs.append(config)

    for market in mainnet_perp_markets:
        config = PerpMarketConfig(
            symbol=decode_name(market.name),
            base_asset_symbol="-".join(decode_name(market.name).split("-")[:-1]),
            market_index=market.market_index,
            oracle=market.amm.oracle,
            oracle_source=market.amm.oracle_source,
        )
        mainnet_configs.append(config)

    output = PERP_MARKET_PREAMBLE
    output += """
devnet_perp_market_configs: list[PerpMarketConfig] = ["""

    for config in devnet_configs:
        output += f"""
    PerpMarketConfig(
        symbol="{config.symbol}",
        base_asset_symbol="{config.base_asset_symbol}",
        market_index={config.market_index},
        oracle=Pubkey.from_string("{str(config.oracle)}"),
        oracle_source=OracleSource.{config.oracle_source.__class__.__name__}(),  # type: ignore
    ),"""

    output += "\n]\n"

    output += """
mainnet_perp_market_configs: list[PerpMarketConfig] = ["""

    for config in mainnet_configs:
        output += f"""
    PerpMarketConfig(
        symbol="{config.symbol}",
        base_asset_symbol="{config.base_asset_symbol}",
        market_index={config.market_index},
        oracle=Pubkey.from_string("{str(config.oracle)}"),
        oracle_source=OracleSource.{config.oracle_source.__class__.__name__}(),  # type: ignore
    ),"""

    output += "\n]\n"

    return output


async def generate_perp_configs(drift_client: DriftClient, env: str) -> str:
    perp_markets = sorted(
        drift_client.get_perp_market_accounts(), key=lambda market: market.market_index
    )

    configs = []
    for market in perp_markets:
        config = PerpMarketConfig(
            symbol=decode_name(market.name),
            base_asset_symbol="-".join(decode_name(market.name).split("-")[:-1]),
            market_index=market.market_index,
            oracle=market.amm.oracle,
            oracle_source=market.amm.oracle_source,
        )
        configs.append(config)

    output = f"""
{env}_perp_market_configs: list[PerpMarketConfig] = ["""

    for config in configs:
        output += f"""
    PerpMarketConfig(
        symbol="{config.symbol}",
        base_asset_symbol="{config.base_asset_symbol}",
        market_index={config.market_index},
        oracle=Pubkey.from_string("{str(config.oracle)}"),
        oracle_source=OracleSource.{config.oracle_source.__class__.__name__}(),  # type: ignore
    ),"""

    output += "\n]\n"

    return output


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--market-type", choices=["perp", "spot"], required=True)
    parser.add_argument("--env", choices=["mainnet", "devnet"], default="mainnet")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the generated constants directly into the target constants file",
    )
    parser.add_argument(
        "--target",
        type=str,
        default=None,
        help="Optional explicit path to constants file to update (overrides default)",
    )
    args = parser.parse_args()

    mainnet_rpc_url = os.getenv("RPC_TRITON")
    devnet_rpc_url = os.getenv("DEVNET_RPC_ENDPOINT")
    if not mainnet_rpc_url or not devnet_rpc_url:
        print(f"RPC URLS are not set {mainnet_rpc_url}, {devnet_rpc_url}")

    drift_client = DriftClient(
        AsyncClient(mainnet_rpc_url),
        Wallet.dummy(),
        env="mainnet",
        account_subscription=AccountSubscriptionConfig("cached"),
    )
    devnet_drift_client = DriftClient(
        AsyncClient(devnet_rpc_url),
        Wallet.dummy(),
        env="devnet",
        account_subscription=AccountSubscriptionConfig("cached"),
    )
    print("Subscribing to Drift Clients 1")
    await drift_client.subscribe()
    print("Subscribed to Drift Clients 1")
    print("Subscribing to Drift Clients 2")
    await devnet_drift_client.subscribe()
    print("Subscribed to Drift Clients 2")

    if args.market_type == "perp" and not args.write:
        output = await generate_perp_configs(drift_client, args.env)
    else:
        output = await generate_spot_configs(drift_client, args.env)

    if args.write:
        repo_root = Path(__file__).resolve().parent.parent
        default_targets = {
            "perp": repo_root / "src" / "driftpy" / "constants" / "perp_markets.py",
            "spot": repo_root / "src" / "driftpy" / "constants" / "spot_markets.py",
        }

        if args.market_type == "perp":
            output = await generate_full_perp_configs(drift_client, devnet_drift_client)
        else:
            output = await generate_full_spot_configs(drift_client, devnet_drift_client)

        target_path = (
            Path(args.target) if args.target else default_targets[args.market_type]
        )
        new_text = output
        target_path.write_text(new_text)
    else:
        print(output)
    await drift_client.unsubscribe()
    await devnet_drift_client.unsubscribe()


if __name__ == "__main__":
    asyncio.run(main())
