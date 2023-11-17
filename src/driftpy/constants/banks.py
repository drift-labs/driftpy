from dataclasses import dataclass
from driftpy.types import OracleSource
from solders.pubkey import Pubkey


@dataclass
class Bank:
    symbol: str
    bank_index: int
    oracle: Pubkey
    oracle_source: OracleSource
    mint: Pubkey


devnet_banks: list[Bank] = [
    Bank(
        symbol="USDC",
        bank_index=0,
        oracle=Pubkey.default(),
        oracle_source=OracleSource.QUOTE_ASSET,
        mint=Pubkey.from_string("8zGuJQqwhZafTah7Uc7Z4tXRnguqkn5KLFAP8oV6PHe2"),
    ),
    Bank(
        symbol="SOL",
        bank_index=1,
        oracle=Pubkey.from_string("J83w4HKfqxwcq3BEMMkPFSppX3gqekLyLJBexebFVkix"),
        oracle_source=OracleSource.PYTH,
        mint=Pubkey.from_string("So11111111111111111111111111111111111111112"),
    ),
    Bank(
        symbol="BTC",
        bank_index=2,
        oracle=Pubkey.from_string("HovQMDrbAgAYPCmHVSrezcSmkMtXSSUsLDFANExrZh2J"),
        oracle_source=OracleSource.PYTH,
        mint=Pubkey.from_string("3BZPwbcqB5kKScF3TEXxwNfx5ipV13kbRVDvfVp5c6fv"),
    ),
]

mainnet_banks: list[Bank] = [
    Bank(
        symbol="USDC",
        bank_index=0,
        oracle=Pubkey.default(),
        oracle_source=OracleSource.QUOTE_ASSET,
        mint=Pubkey.from_string("8zGuJQqwhZafTah7Uc7Z4tXRnguqkn5KLFAP8oV6PHe2"),
    ),
    Bank(
        symbol="SOL",
        bank_index=1,
        oracle=Pubkey.from_string("H6ARHf6YXhGYeQfUzQNGk6rDNnLBQKrenN712K4AQJEG"),
        oracle_source=OracleSource.PYTH,
        mint=Pubkey.from_string("So11111111111111111111111111111111111111112"),
    ),
]
