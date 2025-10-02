import argparse
import asyncio
import os

import dotenv
from anchorpy import Wallet
from solana.rpc.async_api import AsyncClient

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.constants.perp_markets import PerpMarketConfig
from driftpy.constants.spot_markets import SpotMarketConfig
from driftpy.drift_client import DriftClient

dotenv.load_dotenv()


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

    # Generate Python code
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
    args = parser.parse_args()

    if args.env == "mainnet":
        rpc_env_var = "RPC_TRITON"
    else:
        rpc_env_var = f"{args.env.upper()}_RPC_ENDPOINT"
    rpc_url = os.getenv(rpc_env_var)
    if not rpc_url:
        raise ValueError(f"{rpc_env_var} is not set")

    drift_client = DriftClient(
        AsyncClient(rpc_url),
        Wallet.dummy(),
        env=args.env,
        account_subscription=AccountSubscriptionConfig("cached"),
    )

    await drift_client.subscribe()

    if args.market_type == "perp":
        output = await generate_perp_configs(drift_client, args.env)
    else:
        output = await generate_spot_configs(drift_client, args.env)

    print(output)
    await drift_client.unsubscribe()


if __name__ == "__main__":
    asyncio.run(main())
