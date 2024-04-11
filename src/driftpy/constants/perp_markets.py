from dataclasses import dataclass
from solders.pubkey import Pubkey
from driftpy.types import OracleSource


@dataclass
class PerpMarketConfig:
    symbol: str
    base_asset_symbol: str
    market_index: int
    oracle: Pubkey
    oracle_source: OracleSource


devnet_perp_market_configs: list[PerpMarketConfig] = [
    PerpMarketConfig(
        base_asset_symbol="SOL",
        symbol="SOL-PERP",
        market_index=0,
        oracle=Pubkey.from_string("J83w4HKfqxwcq3BEMMkPFSppX3gqekLyLJBexebFVkix"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        base_asset_symbol="BTC",
        symbol="BTC-PERP",
        market_index=1,
        oracle=Pubkey.from_string("HovQMDrbAgAYPCmHVSrezcSmkMtXSSUsLDFANExrZh2J"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        base_asset_symbol="ETH",
        symbol="ETH-PERP",
        market_index=2,
        oracle=Pubkey.from_string("EdVCmQ9FSPcVe5YySXDPCRmc8aDQLKJ9xvYBMZPie1Vw"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        base_asset_symbol="APT",
        symbol="APT-PERP",
        market_index=3,
        oracle=Pubkey.from_string("5d2QJ6u2NveZufmJ4noHja5EHs3Bv1DUMPLG5xfasSVs"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="1MBONK-PERP",
        base_asset_symbol="1MBONK",
        market_index=4,
        oracle=Pubkey.from_string("6bquU99ktV1VRiHDr8gMhDFt3kMfhCQo5nfNrg2Urvsn"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="MATIC-PERP",
        base_asset_symbol="MATIC",
        market_index=5,
        oracle=Pubkey.from_string("FBirwuDFuRAu4iSGc7RGxN5koHB7EJM1wbCmyPuQoGur"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="ARB-PERP",
        base_asset_symbol="ARB",
        market_index=6,
        oracle=Pubkey.from_string("4mRGHzjGerQNWKXyQAmr9kWqb9saPPHKqo1xziXGQ5Dh"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="DOGE-PERP",
        base_asset_symbol="DOGE",
        market_index=7,
        oracle=Pubkey.from_string("4L6YhY8VvUgmqG5MvJkUJATtzB2rFqdrJwQCmFLv4Jzy"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="BNB-PERP",
        base_asset_symbol="BNB",
        market_index=8,
        oracle=Pubkey.from_string("GwzBgrXb4PG59zjce24SF2b9JXbLEjJJTBkmytuEZj1b"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="SUI-PERP",
        base_asset_symbol="SUI",
        market_index=9,
        oracle=Pubkey.from_string("6SK9vS8eMSSj3LUX2dPku93CrNv8xLCp9ng39F39h7A5"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="1MPEPE-PERP",
        base_asset_symbol="1MPEPE",
        market_index=10,
        oracle=Pubkey.from_string("Gz9RfgDeAFSsH7BHDGyNTgCik74rjNwsodJpsCizzmkj"),
        oracle_source=OracleSource.Pyth(),
    ),
]

mainnet_perp_market_configs: list[PerpMarketConfig] = [
    PerpMarketConfig(
        symbol="SOL-PERP",
        base_asset_symbol="SOL",
        market_index=0,
        oracle=Pubkey.from_string("H6ARHf6YXhGYeQfUzQNGk6rDNnLBQKrenN712K4AQJEG"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="BTC-PERP",
        base_asset_symbol="BTC",
        market_index=1,
        oracle=Pubkey.from_string("GVXRSBjFk6e6J3NbVPXohDJetcTjaeeuykUpbQF8UoMU"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="ETH-PERP",
        base_asset_symbol="ETH",
        market_index=2,
        oracle=Pubkey.from_string("JBu1AL4obBcCMqKBBxhpWCNUt136ijcuMZLFvTP7iWdB"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="APT-PERP",
        base_asset_symbol="APT",
        market_index=3,
        oracle=Pubkey.from_string("FNNvb1AFDnDVPkocEri8mWbJ1952HQZtFLuwPiUjSJQ"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="1MBONK-PERP",
        base_asset_symbol="1MBONK",
        market_index=4,
        oracle=Pubkey.from_string("8ihFLu5FimgTQ1Unh4dVyEHUGodJ5gJQCrQf4KUVB9bN"),
        oracle_source=OracleSource.Pyth1M(),
    ),
    PerpMarketConfig(
        symbol="MATIC-PERP",
        base_asset_symbol="MATIC",
        market_index=5,
        oracle=Pubkey.from_string("7KVswB9vkCgeM3SHP7aGDijvdRAHK8P5wi9JXViCrtYh"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="ARB-PERP",
        base_asset_symbol="ARB",
        market_index=6,
        oracle=Pubkey.from_string("5HRrdmghsnU3i2u5StaKaydS7eq3vnKVKwXMzCNKsc4C"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="DOGE-PERP",
        base_asset_symbol="DOGE",
        market_index=7,
        oracle=Pubkey.from_string("FsSM3s38PX9K7Dn6eGzuE29S2Dsk1Sss1baytTQdCaQj"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="BNB-PERP",
        base_asset_symbol="BNB",
        market_index=8,
        oracle=Pubkey.from_string("4CkQJBxhU8EZ2UjhigbtdaPbpTe6mqf811fipYBFbSYN"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="SUI-PERP",
        base_asset_symbol="SUI",
        market_index=9,
        oracle=Pubkey.from_string("3Qub3HaAJaa2xNY7SUqPKd3vVwTqDfDDkEUMPjXD2c1q"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="1MPEPE-PERP",
        base_asset_symbol="1MPEPE",
        market_index=10,
        oracle=Pubkey.from_string("FSfxunDmjjbDV2QxpyxFCAPKmYJHSLnLuvQXDLkMzLBm"),
        oracle_source=OracleSource.Pyth1M(),
    ),
    PerpMarketConfig(
        symbol="OP-PERP",
        base_asset_symbol="OP",
        market_index=11,
        oracle=Pubkey.from_string("4o4CUwzFwLqCvmA5x1G4VzoZkAhAcbiuiYyjWX1CVbY2"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="RNDR-PERP",
        base_asset_symbol="RNDR",
        market_index=12,
        oracle=Pubkey.from_string("CYGfrBJB9HgLf9iZyN4aH5HvUAi2htQ4MjPxeXMf4Egn"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="XRP-PERP",
        base_asset_symbol="XRP",
        market_index=13,
        oracle=Pubkey.from_string("Guffb8DAAxNH6kdoawYjPXTbwUhjmveh8R4LM6uEqRV1"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="HNT-PERP",
        base_asset_symbol="HNT",
        market_index=14,
        oracle=Pubkey.from_string("7moA1i5vQUpfDwSpK6Pw9s56ahB7WFGidtbL2ujWrVvm"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="INJ-PERP",
        base_asset_symbol="INJ",
        market_index=15,
        oracle=Pubkey.from_string("9EdtbaivHQYA4Nh3XzGR6DwRaoorqXYnmpfsnFhvwuVj"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="LINK-PERP",
        base_asset_symbol="LINK",
        market_index=16,
        oracle=Pubkey.from_string("ALdkqQDMfHNg77oCNskfX751kHys4KE7SFuZzuKaN536"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="RLB-PERP",
        base_asset_symbol="RLB",
        market_index=17,
        oracle=Pubkey.from_string("4BA3RcS4zE32WWgp49vvvre2t6nXY1W1kMyKZxeeuUey"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="PYTH-PERP",
        base_asset_symbol="PYTH",
        market_index=18,
        oracle=Pubkey.from_string("nrYkQQQur7z8rYTST3G9GqATviK5SxTDkrqd21MW6Ue"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="TIA-PERP",
        base_asset_symbol="TIA",
        market_index=19,
        oracle=Pubkey.from_string("funeUsHgi2QKkLdUPASRLuYkaK8JaazCEz3HikbkhVt"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="JTO-PERP",
        base_asset_symbol="JTO",
        market_index=20,
        oracle=Pubkey.from_string("D8UUgr8a3aR3yUeHLu7v8FWK7E8Y5sSU7qrYBXUJXBQ5"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="SEI-PERP",
        base_asset_symbol="SEI",
        market_index=21,
        oracle=Pubkey.from_string("6cUuAyAX3eXoiWkjFF77RQBEUF15AAMQ7d1hm4EPd3tv"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="AVAX-PERP",
        base_asset_symbol="AVAX",
        market_index=22,
        oracle=Pubkey.from_string("Ax9ujW5B9oqcv59N8m6f1BpTBq2rGeGaBcpKjC5UYsXU"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="WIF-PERP",
        base_asset_symbol="WIF",
        market_index=23,
        oracle=Pubkey.from_string("6ABgrEZk8urs6kJ1JNdC1sspH5zKXRqxy8sg3ZG2cQps"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="JUP-PERP",
        base_asset_symbol="JUP",
        market_index=24,
        oracle=Pubkey.from_string("g6eRCbboSwK4tSWngn773RCMexr1APQr4uA9bGZBYfo"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="DYM-PERP",
        base_asset_symbol="DYM",
        market_index=25,
        oracle=Pubkey.from_string("CSRRrhXa6DYu1W5jf89A7unCATdug2Z33tYyV2NXZZxa"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="TAO-PERP",
        base_asset_symbol="TAO",
        market_index=26,
        oracle=Pubkey.from_string("5NxzemFgGDhimYE3S5qmb5zkjZUmiHXb4up5WGXe7NLn"),
        oracle_source=OracleSource.Pyth(),
    ),
    PerpMarketConfig(
        symbol="W-PERP",
        base_asset_symbol="W",
        market_index=27,
        oracle=Pubkey.from_string("H9j8CT1bFiWHaZUPMooEaxMRHdWdJ5T9CzFn41z96JHW"),
        oracle_source=OracleSource.Pyth(),
    ),
     PerpMarketConfig(
        symbol="KMNO-PERP",
        base_asset_symbol="KMNO",
        market_index=28,
        oracle=Pubkey.from_string("sDAQaZQJQ4RXAxH3x526mbEXyQZT15ktkL84d7hmk7M"),
        oracle_source=OracleSource.Prelaunch(),
    ),
     PerpMarketConfig(
        symbol="TNSR-PERP",
        base_asset_symbol="TNSR",
        market_index=29,
        oracle=Pubkey.from_string("7Cfyymx49ipGsgEsCA2XygAB2DUsan4C6Cyb5c8oR5st"),
        oracle_source=OracleSource.Switchboard(),
    ),
]
