from typing import Literal, Optional

from driftpy.constants.spot_markets import (
    devnet_spot_market_configs,
    mainnet_spot_market_configs,
    SpotMarketConfig,
)
from driftpy.constants.perp_markets import (
    devnet_perp_market_configs,
    mainnet_perp_market_configs,
    PerpMarketConfig,
)
from dataclasses import dataclass
from solders.pubkey import Pubkey

from anchorpy import Program

from driftpy.types import OracleInfo, SpotMarketAccount

DriftEnv = Literal["devnet", "mainnet"]

DRIFT_PROGRAM_ID = Pubkey.from_string("dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH")


@dataclass
class Config:
    env: DriftEnv
    pyth_oracle_mapping_address: Pubkey
    usdc_mint_address: Pubkey
    default_http: str
    default_ws: str
    perp_markets: list[PerpMarketConfig]
    spot_markets: list[SpotMarketConfig]
    market_lookup_table: Pubkey


configs = {
    "devnet": Config(
        env="devnet",
        pyth_oracle_mapping_address=Pubkey.from_string(
            "BmA9Z6FjioHJPpjT39QazZyhDRUdZy2ezwx4GiDdE2u2"
        ),
        usdc_mint_address=Pubkey.from_string(
            "8zGuJQqwhZafTah7Uc7Z4tXRnguqkn5KLFAP8oV6PHe2"
        ),
        default_http="https://api.devnet.solana.com",
        default_ws="wss://api.devnet.solana.com",
        perp_markets=devnet_perp_market_configs,
        spot_markets=devnet_spot_market_configs,
        market_lookup_table=Pubkey.from_string(
            "FaMS3U4uBojvGn5FSDEPimddcXsCfwkKsFgMVVnDdxGb"
        ),
    ),
    "mainnet": Config(
        env="mainnet",
        pyth_oracle_mapping_address=Pubkey.from_string(
            "AHtgzX45WTKfkPG53L6WYhGEXwQkN1BVknET3sVsLL8J"
        ),
        usdc_mint_address=Pubkey.from_string(
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        ),
        default_http="https://api.mainnet-beta.solana.com",
        default_ws="wss://api.mainnet-beta.solana.com",
        perp_markets=mainnet_perp_market_configs,
        spot_markets=mainnet_spot_market_configs,
        market_lookup_table=Pubkey.from_string(
            "GPZkp76cJtNL2mphCvT6FXkJCVPpouidnacckR6rzKDN"
        ),
    ),
}


async def find_all_market_and_oracles(
    program: Program,
) -> (list[int], list[int], list[OracleInfo]):
    perp_market_indexes = []
    spot_market_indexes = []
    oracle_infos = {}

    perp_markets = await program.account["PerpMarket"].all()
    for perp_market in perp_markets:
        perp_market_indexes.append(perp_market.account.market_index)
        oracle = perp_market.account.amm.oracle
        oracle_source = perp_market.account.amm.oracle_source
        oracle_infos[str(oracle)] = OracleInfo(oracle, oracle_source)

    spot_markets = await program.account["SpotMarket"].all()
    for spot_market in spot_markets:
        spot_market_indexes.append(spot_market.account.market_index)
        oracle = spot_market.account.oracle
        oracle_source = spot_market.account.oracle_source
        oracle_infos[str(oracle)] = OracleInfo(oracle, oracle_source)

    return perp_market_indexes, spot_market_indexes, oracle_infos.values()

async def get_markets_and_oracles(
    drift_client,
    market_indexes: list[int],
    is_perp: bool = True
) -> (list[int], list[OracleInfo]):
    perp_market_indexes, spot_market_indexes, oracle_infos_dict = await find_all_market_and_oracles(drift_client.program)
    oracle_infos = list(oracle_infos_dict)
    filtered_market_indexes = []
    filtered_oracle_infos = []

    if is_perp:
        for index in market_indexes:
            spot_market: SpotMarketAccount = drift_client.get_spot_market_account(index)
            oracle_pubkey = str(spot_market.oracle)
            oracle_info = next((info for info in oracle_infos if str(info.pubkey) == oracle_pubkey), None)
            filtered_market_indexes.append(index)
            filtered_oracle_infos.append(oracle_info)
    else:
        for index in market_indexes:
            perp_market = drift_client.get_perp_market_account(index)
            oracle_pubkey = str(perp_market.oracle)
            oracle_info = next((info for info in oracle_infos if str(info.pubkey) == oracle_pubkey), None)
            filtered_market_indexes.append(index)
            filtered_oracle_infos.append(oracle_info)

    return filtered_market_indexes, filtered_oracle_infos
