import asyncio
from base64 import b64decode
from typing import Literal, Optional, Sequence, Tuple, Union

import jsonrpcclient
from driftpy.accounts.oracle import decode_oracle, decode_pyth_price_info
from driftpy.accounts.types import DataAndSlot, FullOracleWrapper

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

from driftpy.types import (
    OracleInfo,
    OraclePriceData,
    OracleSource,
    PerpMarketAccount,
    SpotMarketAccount,
)

DriftEnv = Literal["devnet", "mainnet"]

DRIFT_PROGRAM_ID = Pubkey.from_string("dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH")
SEQUENCER_PROGRAM_ID = Pubkey.from_string(
    "GDDMwNyyx8uB6zrqwBFHjLLG3TBYk2F8Az4yrQC5RzMp"
)
DEVNET_SEQUENCER_PROGRAM_ID = Pubkey.from_string(
    "FBngRHN4s5cmHagqy3Zd6xcK3zPJBeX5DixtHFbBhyCn"
)


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
            "D9cnvzswDikQDf53k4HpQ3KJ9y1Fv3HGGDFYMXnK5T6c"
        ),
    ),
}


async def find_all_market_and_oracles(
    program: Program, data_and_slots: bool = False
) -> Tuple[
    Union[list[int], list[DataAndSlot[PerpMarketAccount]]],
    Union[list[int], list[DataAndSlot[SpotMarketAccount]]],
    Union[list[OracleInfo], list[FullOracleWrapper]],
]:
    if not data_and_slots:
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
    else:
        perp_markets = []
        spot_markets = []
        oracle_infos = {}

        perp_filters = [{"memcmp": {"offset": 0, "bytes": "2pTyMkwXuti"}}]
        spot_filters = [{"memcmp": {"offset": 0, "bytes": "HqqNdyfVbzv"}}]

        perp_request = jsonrpcclient.request(
            "getProgramAccounts",
            [
                str(program.program_id),
                {"filters": perp_filters, "encoding": "base64", "withContext": True},
            ],
        )

        post = program.provider.connection._provider.session.post(
            program.provider.connection._provider.endpoint_uri,
            json=perp_request,
            headers={"content-encoding": "gzip"},
        )

        resp = await asyncio.wait_for(post, timeout=10)

        parsed_resp = jsonrpcclient.parse(resp.json())

        perp_slot = int(parsed_resp.result["context"]["slot"])

        perp_markets: list[PerpMarketAccount] = [
            decode_account(account["account"]["data"][0], program)
            for account in parsed_resp.result["value"]
        ]

        perp_ds: list[DataAndSlot] = [
            DataAndSlot(perp_slot, perp_market) for perp_market in perp_markets
        ]

        spot_request = jsonrpcclient.request(
            "getProgramAccounts",
            [
                str(program.program_id),
                {"filters": spot_filters, "encoding": "base64", "withContext": True},
            ],
        )

        post = program.provider.connection._provider.session.post(
            program.provider.connection._provider.endpoint_uri,
            json=spot_request,
            headers={"content-encoding": "gzip"},
        )

        resp = await asyncio.wait_for(post, timeout=10)

        parsed_resp = jsonrpcclient.parse(resp.json())

        spot_slot = int(parsed_resp.result["context"]["slot"])

        spot_markets: list[SpotMarketAccount] = [
            decode_account(account["account"]["data"][0], program)
            for account in parsed_resp.result["value"]
        ]

        spot_ds: list[DataAndSlot] = [
            DataAndSlot(spot_slot, spot_market) for spot_market in spot_markets
        ]

        oracle_infos.update(
            {market.amm.oracle: market.amm.oracle_source for market in perp_markets}
        )
        oracle_infos.update(
            {market.oracle: market.oracle_source for market in spot_markets}
        )

        oracle_keys = list(oracle_infos.keys())

        oracle_ais = await program.provider.connection.get_multiple_accounts(
            oracle_keys
        )

        oracle_slot = oracle_ais.context.slot

        oracle_price_datas = [
            decode_oracle(account.data, oracle_infos[oracle_keys[i]])
            for i, account in enumerate(oracle_ais.value)
            if account is not None
        ]

        oracle_ds: list[DataAndSlot] = [
            DataAndSlot(oracle_slot, oracle_price_data)
            for oracle_price_data in oracle_price_datas
        ]

        full_oracle_wrappers: list[FullOracleWrapper] = [
            FullOracleWrapper(
                pubkey=oracle_keys[i],
                oracle_source=oracle_infos[oracle_keys[i]],
                oracle_price_data_and_slot=oracle_ds[i],
            )
            for i in range(len(oracle_keys))
            if oracle_ais.value[i] is not None
        ]

        return perp_ds, spot_ds, full_oracle_wrappers


def decode_account(account_data: str, program: Program):
    decoded_data = b64decode(account_data)
    return program.coder.accounts.decode(decoded_data)


def find_market_config_by_index(
    market_configs: list[Union[SpotMarketConfig, PerpMarketConfig]], market_index: int
) -> Optional[Union[SpotMarketConfig, PerpMarketConfig]]:
    for config in market_configs:
        if hasattr(config, "market_index") and config.market_index == market_index:
            return config
    return None


def get_markets_and_oracles(
    env: DriftEnv = "mainnet",
    perp_markets: Optional[Sequence[int]] = None,
    spot_markets: Optional[Sequence[int]] = None,
):
    config = configs[env]
    spot_market_oracle_infos = []
    perp_market_oracle_infos = []
    spot_market_indexes = []

    if perp_markets is None and spot_markets is None:
        raise ValueError("no indexes provided")

    if spot_markets is not None:
        for spot_market_index in spot_markets:
            market_config = find_market_config_by_index(
                config.spot_markets, spot_market_index
            )
            spot_market_oracle_infos.append(
                OracleInfo(market_config.oracle, market_config.oracle_source)
            )

    if perp_markets is not None:
        spot_market_indexes.append(0)
        spot_market_oracle_infos.append(
            OracleInfo(
                config.spot_markets[0].oracle, config.spot_markets[0].oracle_source
            )
        )
        for perp_market_index in perp_markets:
            market_config = find_market_config_by_index(
                config.perp_markets, perp_market_index
            )
            perp_market_oracle_infos.append(
                OracleInfo(market_config.oracle, market_config.oracle_source)
            )

    return spot_market_oracle_infos, perp_market_oracle_infos, spot_market_indexes
