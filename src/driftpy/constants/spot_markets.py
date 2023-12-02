from dataclasses import dataclass
from driftpy.types import OracleSource
from solders.pubkey import Pubkey


@dataclass
class SpotMarketConfig:
    symbol: str
    market_index: int
    oracle: Pubkey
    oracle_source: OracleSource
    mint: Pubkey


devnet_spot_market_configs: list[SpotMarketConfig] = [
    SpotMarketConfig(
        symbol="USDC",
        market_index=0,
        oracle=Pubkey.default(),
        oracle_source=OracleSource.QuoteAsset,
        mint=Pubkey.from_string("8zGuJQqwhZafTah7Uc7Z4tXRnguqkn5KLFAP8oV6PHe2"),
    ),
    SpotMarketConfig(
        symbol="SOL",
        market_index=1,
        oracle=Pubkey.from_string("J83w4HKfqxwcq3BEMMkPFSppX3gqekLyLJBexebFVkix"),
        oracle_source=OracleSource.Pyth,
        mint=Pubkey.from_string("So11111111111111111111111111111111111111112"),
    ),
    SpotMarketConfig(
        symbol="BTC",
        market_index=2,
        oracle=Pubkey.from_string("HovQMDrbAgAYPCmHVSrezcSmkMtXSSUsLDFANExrZh2J"),
        oracle_source=OracleSource.Pyth,
        mint=Pubkey.from_string("3BZPwbcqB5kKScF3TEXxwNfx5ipV13kbRVDvfVp5c6fv"),
    ),
]

mainnet_spot_market_configs: list[SpotMarketConfig] = [
    SpotMarketConfig(
        symbol="USDC",
        market_index=0,
        oracle=Pubkey.default(),
        oracle_source=OracleSource.QuoteAsset,
        mint=Pubkey.from_string("8zGuJQqwhZafTah7Uc7Z4tXRnguqkn5KLFAP8oV6PHe2"),
    ),
    SpotMarketConfig(
        symbol="SOL",
        market_index=1,
        oracle=Pubkey.from_string("H6ARHf6YXhGYeQfUzQNGk6rDNnLBQKrenN712K4AQJEG"),
        oracle_source=OracleSource.Pyth,
        mint=Pubkey.from_string("So11111111111111111111111111111111111111112"),
    ),
]
