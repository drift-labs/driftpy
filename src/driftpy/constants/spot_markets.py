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
        oracle_source=OracleSource.QuoteAsset(),
        mint=Pubkey.from_string("8zGuJQqwhZafTah7Uc7Z4tXRnguqkn5KLFAP8oV6PHe2"),
    ),
    SpotMarketConfig(
        symbol="SOL",
        market_index=1,
        oracle=Pubkey.from_string("J83w4HKfqxwcq3BEMMkPFSppX3gqekLyLJBexebFVkix"),
        oracle_source=OracleSource.Pyth(),
        mint=Pubkey.from_string("So11111111111111111111111111111111111111112"),
    ),
    SpotMarketConfig(
        symbol="BTC",
        market_index=2,
        oracle=Pubkey.from_string("HovQMDrbAgAYPCmHVSrezcSmkMtXSSUsLDFANExrZh2J"),
        oracle_source=OracleSource.Pyth(),
        mint=Pubkey.from_string("3BZPwbcqB5kKScF3TEXxwNfx5ipV13kbRVDvfVp5c6fv"),
    ),
]

mainnet_spot_market_configs: list[SpotMarketConfig] = [
    SpotMarketConfig(
        symbol="USDC",
        market_index=0,
        oracle=Pubkey.from_string("Gnt27xtC473ZT2Mw5u8wZ68Z3gULkSTb5DuxJy7eJotD"),
        oracle_source=OracleSource.PythStableCoin(),
        mint=Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"),
    ),
    SpotMarketConfig(
        symbol="SOL",
        market_index=1,
        oracle=Pubkey.from_string("H6ARHf6YXhGYeQfUzQNGk6rDNnLBQKrenN712K4AQJEG"),
        oracle_source=OracleSource.Pyth(),
        mint=Pubkey.from_string("So11111111111111111111111111111111111111112"),
    ),
    SpotMarketConfig(
        symbol="mSOL",
        market_index=2,
        oracle=Pubkey.from_string("E4v1BBgoso9s64TQvmyownAVJbhbEPGyzA3qn4n46qj9"),
        oracle_source=OracleSource.Pyth(),
        mint=Pubkey.from_string("mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So"),
    ),
    SpotMarketConfig(
        symbol="wBTC",
        market_index=3,
        oracle=Pubkey.from_string("GVXRSBjFk6e6J3NbVPXohDJetcTjaeeuykUpbQF8UoMU"),
        oracle_source=OracleSource.Pyth(),
        mint=Pubkey.from_string("3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh"),
    ),
    SpotMarketConfig(
        symbol="wETH",
        market_index=4,
        oracle=Pubkey.from_string("JBu1AL4obBcCMqKBBxhpWCNUt136ijcuMZLFvTP7iWdB"),
        oracle_source=OracleSource.Pyth(),
        mint=Pubkey.from_string("7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs"),
    ),
    SpotMarketConfig(
        symbol="USDT",
        market_index=5,
        oracle=Pubkey.from_string("3vxLXJqLqF3JG5TCbYycbKWRBbCJQLxQmBGCkyqEEefL"),
        oracle_source=OracleSource.Pyth(),
        mint=Pubkey.from_string("Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"),
    ),
    SpotMarketConfig(
        symbol="jitoSOL",
        market_index=6,
        oracle=Pubkey.from_string("7yyaeuJ1GGtVBLT2z2xub5ZWYKaNhF28mj1RdV4VDFVk"),
        oracle_source=OracleSource.Pyth(),
        mint=Pubkey.from_string("J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn"),
    ),
    SpotMarketConfig(
        symbol="SOL",
        market_index=7,
        oracle=Pubkey.from_string("nrYkQQQur7z8rYTST3G9GqATviK5SxTDkrqd21MW6Ue"),
        oracle_source=OracleSource.Pyth(),
        mint=Pubkey.from_string("HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3"),
    ),
    SpotMarketConfig(
        symbol="bSOL",
        market_index=8,
        oracle=Pubkey.from_string("AFrYBhb5wKQtxRS9UA9YRS4V3dwFm7SqmS6DHKq6YVgo"),
        oracle_source=OracleSource.Pyth(),
        mint=Pubkey.from_string("bSo13r4TkiE4KumL71LsHTPpL2euBYLFx6h9HP3piy1"),
    ),
    SpotMarketConfig(
        symbol="JTO",
        market_index=9,
        oracle=Pubkey.from_string("D8UUgr8a3aR3yUeHLu7v8FWK7E8Y5sSU7qrYBXUJXBQ5"),
        oracle_source=OracleSource.Pyth(),
        mint=Pubkey.from_string("jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL"),
    ),
]
