"""
This file contains the market configs for the spot markets on Drift.

For reference, see the TypeScript implementation:
- https://github.com/drift-labs/protocol-v2/blob/master/sdk/src/constants/spotMarkets.ts
"""

from dataclasses import dataclass

from solders.pubkey import Pubkey  # type: ignore

from driftpy.types import OracleSource


@dataclass
class SpotMarketConfig:
    symbol: str
    market_index: int
    oracle: Pubkey
    oracle_source: OracleSource
    mint: Pubkey


WRAPPED_SOL_MINT = Pubkey.from_string("So11111111111111111111111111111111111111112")

devnet_spot_market_configs: list[SpotMarketConfig] = [
    SpotMarketConfig(
        symbol="USDC",
        market_index=0,
        oracle=Pubkey.from_string("En8hkHLkRe9d9DraYmBTrus518BvmVH448YcvmrFM6Ce"),
        oracle_source=OracleSource.PythStableCoinPull(),  # type: ignore
        mint=Pubkey.from_string("8zGuJQqwhZafTah7Uc7Z4tXRnguqkn5KLFAP8oV6PHe2"),
    ),
    SpotMarketConfig(
        symbol="SOL",
        market_index=1,
        oracle=Pubkey.from_string("BAtFj4kQttZRVep3UZS2aZRDixkGYgWsbqTBVDbnSsPF"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=WRAPPED_SOL_MINT,
    ),
    SpotMarketConfig(
        symbol="BTC",
        market_index=2,
        oracle=Pubkey.from_string("486kr3pmFPfTsS4aZgcsQ7kS4i9rjMsYYZup6HQNSTT4"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("3BZPwbcqB5kKScF3TEXxwNfx5ipV13kbRVDvfVp5c6fv"),
    ),
    SpotMarketConfig(
        symbol="PYUSD",
        market_index=3,
        oracle=Pubkey.from_string("HpMoKp3TCd3QT4MWYUKk2zCBwmhr5Df45fB6wdxYqEeh"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("GLfF72ZCUnS6N9iDJw8kedHzd6WFVf3VbpwdKKy76FRk"),
    ),
    SpotMarketConfig(
        symbol="BONK",
        market_index=4,
        oracle=Pubkey.from_string("GojbSnJuPdKDT1ZuHuAM5t9oz6bxTo1xhUKpTua2F72p"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("7SekVZDmKCCDgTP8m6Hk4CfexFSru9RkwDCczmcwcsP6"),
    ),
    SpotMarketConfig(
        symbol="JLP",
        market_index=5,
        oracle=Pubkey.from_string("5Mb11e5rt1Sp6A286B145E4TmgMzsM2UX9nCF2vas5bs"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("HGe9FejFyhWSx6zdvx2RjynX7rmoEXFiJiLU437NXemZ"),
    ),
    SpotMarketConfig(
        symbol="USDC",
        market_index=6,
        oracle=Pubkey.from_string("En8hkHLkRe9d9DraYmBTrus518BvmVH448YcvmrFM6Ce"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("8zGuJQqwhZafTah7Uc7Z4tXRnguqkn5KLFAP8oV6PHe2"),
    ),
]

mainnet_spot_market_configs: list[SpotMarketConfig] = [
    SpotMarketConfig(
        symbol="USDC",
        market_index=0,
        oracle=Pubkey.from_string("En8hkHLkRe9d9DraYmBTrus518BvmVH448YcvmrFM6Ce"),
        oracle_source=OracleSource.PythStableCoinPull(),  # type: ignore
        mint=Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"),
    ),
    SpotMarketConfig(
        symbol="SOL",
        market_index=1,
        oracle=Pubkey.from_string("BAtFj4kQttZRVep3UZS2aZRDixkGYgWsbqTBVDbnSsPF"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=WRAPPED_SOL_MINT,
    ),
    SpotMarketConfig(
        symbol="mSOL",
        market_index=2,
        oracle=Pubkey.from_string("FAq7hqjn7FWGXKDwJHzsXGgBcydGTcK4kziJpAGWXjDb"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So"),
    ),
    SpotMarketConfig(
        symbol="wBTC",
        market_index=3,
        oracle=Pubkey.from_string("9Tq8iN5WnMX2PcZGj4iSFEAgHCi8cM6x8LsDUbuzq8uw"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh"),
    ),
    SpotMarketConfig(
        symbol="wETH",
        market_index=4,
        oracle=Pubkey.from_string("6bEp2MiyoiiiDxcVqE8rUHQWwHirXUXtKfAEATTVqNzT"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs"),
    ),
    SpotMarketConfig(
        symbol="USDT",
        market_index=5,
        oracle=Pubkey.from_string("BekJ3P5G3iFeC97sXHuKnUHofCFj9Sbo7uyF2fkKwvit"),
        oracle_source=OracleSource.PythStableCoinPull(),  # type: ignore
        mint=Pubkey.from_string("Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"),
    ),
    SpotMarketConfig(
        symbol="jitoSOL",
        market_index=6,
        oracle=Pubkey.from_string("9QE1P5EfzthYDgoQ9oPeTByCEKaRJeZbVVqKJfgU9iau"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn"),
    ),
    SpotMarketConfig(
        symbol="PYTH",
        market_index=7,
        oracle=Pubkey.from_string("GqkCu7CbsPVz1H6W6AAHuReqbJckYG59TXz7Y5HDV7hr"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3"),
    ),
    SpotMarketConfig(
        symbol="bSOL",
        market_index=8,
        oracle=Pubkey.from_string("BmDWPMsytWmYkh9n6o7m79eVshVYf2B5GVaqQ2EWKnGH"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("bSo13r4TkiE4KumL71LsHTPpL2euBYLFx6h9HP3piy1"),
    ),
    SpotMarketConfig(
        symbol="JTO",
        market_index=9,
        oracle=Pubkey.from_string("Ffq6ACJ17NAgaxC6ocfMzVXL3K61qxB2xHg6WUawWPfP"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL"),
    ),
    SpotMarketConfig(
        symbol="WIF",
        market_index=10,
        oracle=Pubkey.from_string("6x6KfE7nY2xoLCRSMPT1u83wQ5fpGXoKNBqFjrCwzsCQ"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"),
    ),
    SpotMarketConfig(
        symbol="JUP",
        market_index=11,
        oracle=Pubkey.from_string("AwqRpfJ36jnSZQykyL1jYY35mhMteeEAjh7o8LveRQin"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"),
    ),
    SpotMarketConfig(
        symbol="RNDR",
        market_index=12,
        oracle=Pubkey.from_string("8TQztfGcNjHGRusX4ejQQtPZs3Ypczt9jWF6pkgQMqUX"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof"),
    ),
    SpotMarketConfig(
        symbol="W",
        market_index=13,
        oracle=Pubkey.from_string("4HbitGsdcFbtFotmYscikQFAAKJ3nYx4t7sV7fTvsk8U"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("85VBFQZC9TZkfaptBWjvUw7YbZjy52A6mjtPGjstQAmQ"),
    ),
    SpotMarketConfig(
        symbol="TNSR",
        market_index=14,
        oracle=Pubkey.from_string("13jpjpVyU5hGpjsZ4HzCcmBo85wze4N8Au7U6cC3GMip"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("TNSRxcUxoT9xBG3de7PiJyTDYu7kskLqcpddxnEJAS6"),
    ),
    SpotMarketConfig(
        symbol="DRIFT",
        market_index=15,
        oracle=Pubkey.from_string("23KmX7SNikmUr2axSCy6Zer7XPBnvmVcASALnDGqBVRR"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("DriFtupJYLTosbwoN8koMbEYSx54aFAVLddWsbksjwg7"),
    ),
    SpotMarketConfig(
        symbol="INF",
        market_index=16,
        oracle=Pubkey.from_string("B7RUYg2zF6UdUSHv2RmpnriPVJccYWojgFydNS1NY5F8"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("5oVNBeEEQvYi1cX3ir8Dx5n1P7pdxydbGF2X4TxVusJm"),
    ),
    SpotMarketConfig(
        symbol="dSOL",
        market_index=17,
        oracle=Pubkey.from_string("4YstsHafLyDbYFxmJbgoEr33iJJEp6rNPgLTQRgXDkG2"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("Dso1bDeDjCQxTrWHqUUi63oBvV7Mdm6WaobLbQ7gnPQ"),
    ),
    SpotMarketConfig(
        symbol="USDY",
        market_index=18,
        oracle=Pubkey.from_string("BPTQgHV4y2x4jvKPPkkd9aS8jY7L3DGZBwjEZC8Vm27o"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("A1KLoBrKBde8Ty9qtNQUtq3C2ortoC3u7twggz7sEto6"),
    ),
    SpotMarketConfig(
        symbol="JLP",
        market_index=19,
        oracle=Pubkey.from_string("5Mb11e5rt1Sp6A286B145E4TmgMzsM2UX9nCF2vas5bs"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4"),
    ),
    SpotMarketConfig(
        symbol="POPCAT",
        market_index=20,
        oracle=Pubkey.from_string("H3pn43tkNvsG5z3qzmERguSvKoyHZvvY6VPmNrJqiW5X"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"),
    ),
    SpotMarketConfig(
        symbol="CLOUD",
        market_index=21,
        oracle=Pubkey.from_string("FNFejcXENaPgKaCTfstew9vSSvdQPnXjGTkJjUnnYvHU"),
        oracle_source=OracleSource.SwitchboardOnDemand(),  # type: ignore
        mint=Pubkey.from_string("CLoUDKc4Ane7HeQcPpE3YHnznRxhMimJ4MyaUqyHFzAu"),
    ),
    SpotMarketConfig(
        symbol="PYUSD",
        market_index=22,
        oracle=Pubkey.from_string("HpMoKp3TCd3QT4MWYUKk2zCBwmhr5Df45fB6wdxYqEeh"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo"),
    ),
    SpotMarketConfig(
        symbol="USDe",
        market_index=23,
        oracle=Pubkey.from_string("BXej5boX2nWudwAfZQedo212B9XJxhjTeeF3GbCwXmYa"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("DEkqHyPN7GMRJ5cArtQFAWefqbZb33Hyf6s5iCwjEonT"),
    ),
    SpotMarketConfig(
        symbol="sUSDe",
        market_index=24,
        oracle=Pubkey.from_string("BRuNuzLAPHHGSSVAJPKMcmJMdgDfrekvnSxkxPDGdeqp"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("Eh6XEPhSwoLv5wFApukmnaVSHQ6sAnoD9BmgmwQoN2sN"),
    ),
    SpotMarketConfig(
        symbol="BNSOL",
        market_index=25,
        oracle=Pubkey.from_string("8DmXTfhhtb9kTcpTVfb6Ygx8WhZ8wexGqcpxfn23zooe"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("BNso1VUJnh4zcfpZa6986Ea66P6TCp59hvtNJ8b1X85"),
    ),
    SpotMarketConfig(
        symbol="MOTHER",
        market_index=26,
        oracle=Pubkey.from_string("56ap2coZG7FPWUigVm9XrpQs3xuCwnwQaWtjWZcffEUG"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("3S8qX1MsMqRbiwKg2cQyx7nis1oHMgaCuc9c4VfvVdPN"),
    ),
    SpotMarketConfig(
        symbol="cbBTC",
        market_index=27,
        oracle=Pubkey.from_string("486kr3pmFPfTsS4aZgcsQ7kS4i9rjMsYYZup6HQNSTT4"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("cbbtcf3aa214zXHbiAZQwf4122FBYbraNdFqgw4iMij"),
    ),
    SpotMarketConfig(
        symbol="USDS",
        market_index=28,
        oracle=Pubkey.from_string("7pT9mxKXyvfaZKeKy1oe2oV2K1RFtF7tPEJHUY3h2vVV"),
        oracle_source=OracleSource.PythStableCoinPull(),  # type: ignore
        mint=Pubkey.from_string("USDSwr9ApdHk5bvJKMjzff41FfuX8bSxdKcR81vTwcA"),
    ),
    SpotMarketConfig(
        symbol="META",
        market_index=29,
        oracle=Pubkey.from_string("DwYF1yveo8XTF1oqfsqykj332rjSxAd7bR6Gu6i4iUET"),
        oracle_source=OracleSource.SwitchboardOnDemand(),  # type: ignore
        mint=Pubkey.from_string("METADDFL6wWMWEoKTFJwcThTbUmtarRJZjRpzUvkxhr"),
    ),
    SpotMarketConfig(
        symbol="ME",
        market_index=30,
        oracle=Pubkey.from_string("FLQjrmEPGwbCKRYZ1eYM5FPccHBrCv2cN4GBu3mWfmPH"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("MEFNBXixkEbait3xn9bkm8WsJzXtVsaJEn4c8Sam21u"),
    ),
    SpotMarketConfig(
        symbol="PENGU",
        market_index=31,
        oracle=Pubkey.from_string("7vGHChuBJyFMYBqMLXRzBmRxWdSuwEmg8RvRm3RWQsxi"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv"),
    ),
    SpotMarketConfig(
        symbol="BONK",
        market_index=32,
        oracle=Pubkey.from_string("GojbSnJuPdKDT1ZuHuAM5t9oz6bxTo1xhUKpTua2F72p"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"),
    ),
    SpotMarketConfig(
        symbol="JLP",
        market_index=33,
        oracle=Pubkey.from_string("5Mb11e5rt1Sp6A286B145E4TmgMzsM2UX9nCF2vas5bs"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4"),
    ),
    SpotMarketConfig(
        symbol="USDC",
        market_index=34,
        oracle=Pubkey.from_string("En8hkHLkRe9d9DraYmBTrus518BvmVH448YcvmrFM6Ce"),
        oracle_source=OracleSource.PythStableCoinPull(),  # type: ignore
        mint=Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"),
    ),
    SpotMarketConfig(
        symbol="AI16Z",
        market_index=35,
        oracle=Pubkey.from_string("3gdGkrmBdYR7B1MRRdRVysqhZCvYvLGHonr9b7o9WVki"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("HeLp6NuQkmYB4pYWo2zYs22mESHXPQYzXbB8n4V98jwC"),
    ),
    SpotMarketConfig(
        symbol="TRUMP",
        market_index=36,
        oracle=Pubkey.from_string("AmSLxftd19EPDR9NnZDxvdStqtRW7k9zWto7FfGaz24K"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN"),
    ),
    SpotMarketConfig(
        symbol="MELANIA",
        market_index=37,
        oracle=Pubkey.from_string("28Zk42cxbg4MxiTewSwoedvW6MUgjoVHSTvTW7zQ7ESi"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
        mint=Pubkey.from_string("FUAfBo2jgks6gB4Z4LfZkqSZgzNucisEHqnNebaRxM1P"),
    ),
]
