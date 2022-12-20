from dataclasses import dataclass
from driftpy.types import OracleSource
from solana.publickey import PublicKey


@dataclass
class Bank:
    symbol: str
    bank_index: int
    oracle: PublicKey
    oracle_source: OracleSource
    mint: PublicKey


devnet_banks: list[Bank] = [
    Bank(
        symbol="USDC",
        bank_index=0,
        oracle=PublicKey(0),
        oracle_source=OracleSource.QUOTE_ASSET,
        mint=PublicKey("8zGuJQqwhZafTah7Uc7Z4tXRnguqkn5KLFAP8oV6PHe2"),
    ),
    Bank(
        symbol="SOL",
        bank_index=1,
        oracle=PublicKey("J83w4HKfqxwcq3BEMMkPFSppX3gqekLyLJBexebFVkix"),
        oracle_source=OracleSource.PYTH,
        mint=PublicKey("So11111111111111111111111111111111111111112"),
    ),
    Bank(
        symbol="BTC",
        bank_index=2,
        oracle=PublicKey("HovQMDrbAgAYPCmHVSrezcSmkMtXSSUsLDFANExrZh2J"),
        oracle_source=OracleSource.PYTH,
        mint=PublicKey("3BZPwbcqB5kKScF3TEXxwNfx5ipV13kbRVDvfVp5c6fv"),
    ),
]

mainnet_banks: list[Bank] = [
    Bank(
        symbol="USDC",
        bank_index=0,
        oracle=PublicKey(0),
        oracle_source=OracleSource.QUOTE_ASSET,
        mint=PublicKey("8zGuJQqwhZafTah7Uc7Z4tXRnguqkn5KLFAP8oV6PHe2"),
    ),
    Bank(
        symbol="SOL",
        bank_index=1,
        oracle=PublicKey("H6ARHf6YXhGYeQfUzQNGk6rDNnLBQKrenN712K4AQJEG"),
        oracle_source=OracleSource.PYTH,
        mint=PublicKey("So11111111111111111111111111111111111111112"),
    ),
]
