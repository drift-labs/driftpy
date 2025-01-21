from dataclasses import dataclass

from solders.pubkey import Pubkey  # type: ignore

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
        symbol="SOL-PERP",
        base_asset_symbol="SOL",
        market_index=0,
        oracle=Pubkey.from_string("3m6i4RFWEDw2Ft4tFHPJtYgmpPe21k56M3FHeWYrgGBz"),
        oracle_source=OracleSource.PythLazer(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="BTC-PERP",
        base_asset_symbol="BTC",
        market_index=1,
        oracle=Pubkey.from_string("35MbvS1Juz2wf7GsyHrkCw8yfKciRLxVpEhfZDZFrB4R"),
        oracle_source=OracleSource.PythLazer(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="ETH-PERP",
        base_asset_symbol="ETH",
        market_index=2,
        oracle=Pubkey.from_string("93FG52TzNKCnMiasV14Ba34BYcHDb9p4zK4GjZnLwqWR"),
        oracle_source=OracleSource.PythLazer(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="APT-PERP",
        base_asset_symbol="APT",
        market_index=3,
        oracle=Pubkey.from_string("79EWaCYU9jiQN8SbvVzGFAhAncUZYp3PjNg7KxmN5cLE"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="1MBONK-PERP",
        base_asset_symbol="1MBONK",
        market_index=4,
        oracle=Pubkey.from_string("GojbSnJuPdKDT1ZuHuAM5t9oz6bxTo1xhUKpTua2F72p"),
        oracle_source=OracleSource.Pyth1MPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="MATIC-PERP",
        base_asset_symbol="MATIC",
        market_index=5,
        oracle=Pubkey.from_string("BrzyDgwELy4jjjsqLQpBeUxzrsueYyMhuWpYBaUYcXvi"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="ARB-PERP",
        base_asset_symbol="ARB",
        market_index=6,
        oracle=Pubkey.from_string("8ocfAdqVRnzvfdubQaTxar4Kz5HJhNbPNmkLxswqiHUD"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="DOGE-PERP",
        base_asset_symbol="DOGE",
        market_index=7,
        oracle=Pubkey.from_string("23y63pHVwKfYSCDFdiGRaGbTYWoyr8UzhUE7zukyf6gK"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="BNB-PERP",
        base_asset_symbol="BNB",
        market_index=8,
        oracle=Pubkey.from_string("Dk8eWjuQHMbxJAwB9Sg7pXQPH4kgbg8qZGcUrWcD9gTm"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="SUI-PERP",
        base_asset_symbol="SUI",
        market_index=9,
        oracle=Pubkey.from_string("HBordkz5YxjzNURmKUY4vfEYFG9fZyZNeNF1VDLMoemT"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="1MPEPE-PERP",
        base_asset_symbol="1MPEPE",
        market_index=10,
        oracle=Pubkey.from_string("CLxofhtzvLiErpn25wvUzpZXEqBhuZ6WMEckEraxyuGt"),
        oracle_source=OracleSource.Pyth1MPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="OP-PERP",
        base_asset_symbol="OP",
        market_index=11,
        oracle=Pubkey.from_string("C9Zi2Y3Mt6Zt6pcFvobN3N29HcrzKujPAPBDDTDRcUa2"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="RNDR-PERP",
        base_asset_symbol="RNDR",
        market_index=12,
        oracle=Pubkey.from_string("8TQztfGcNjHGRusX4ejQQtPZs3Ypczt9jWF6pkgQMqUX"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="XRP-PERP",
        base_asset_symbol="XRP",
        market_index=13,
        oracle=Pubkey.from_string("9757epAjXWCWQH98kyK9vzgehd1XDVEf7joNHUaKk3iV"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="HNT-PERP",
        base_asset_symbol="HNT",
        market_index=14,
        oracle=Pubkey.from_string("9b1rcK9RUPK2vAqwNYCYEG34gUVpS2WGs2YCZZy2X5Tb"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="INJ-PERP",
        base_asset_symbol="INJ",
        market_index=15,
        oracle=Pubkey.from_string("BfXcyDWJmYADa5eZD7gySSDd6giqgjvm7xsAhQ239SUD"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="LINK-PERP",
        base_asset_symbol="LINK",
        market_index=16,
        oracle=Pubkey.from_string("Gwvob7yoLMgQRVWjScCRyQFMsgpRKrSAYisYEyjDJwEp"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="RLB-PERP",
        base_asset_symbol="RLB",
        market_index=17,
        oracle=Pubkey.from_string("4CyhPqyVK3UQHFWhEpk91Aw4WbBsN3JtyosXH6zjoRqG"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="PYTH-PERP",
        base_asset_symbol="PYTH",
        market_index=18,
        oracle=Pubkey.from_string("GqkCu7CbsPVz1H6W6AAHuReqbJckYG59TXz7Y5HDV7hr"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="TIA-PERP",
        base_asset_symbol="TIA",
        market_index=19,
        oracle=Pubkey.from_string("C6LHPUrgjrgo5eNUitC8raNEdEttfoRhmqdJ3BHVBJhi"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="JTO-PERP",
        base_asset_symbol="JTO",
        market_index=20,
        oracle=Pubkey.from_string("Ffq6ACJ17NAgaxC6ocfMzVXL3K61qxB2xHg6WUawWPfP"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="SEI-PERP",
        base_asset_symbol="SEI",
        market_index=21,
        oracle=Pubkey.from_string("EVyoxFo5jWpv1vV7p6KVjDWwVqtTqvrZ4JMFkieVkVsD"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="AVAX-PERP",
        base_asset_symbol="AVAX",
        market_index=22,
        oracle=Pubkey.from_string("FgBGHNex4urrBmNbSj8ntNQDGqeHcWewKtkvL6JE6dEX"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="W-PERP",
        base_asset_symbol="W",
        market_index=23,
        oracle=Pubkey.from_string("J9nrFWjDUeDVZ4BhhxsbQXWgLcLEgQyNBrCbwSADmJdr"),
        oracle_source=OracleSource.SwitchboardOnDemand(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="KMNO-PERP",
        base_asset_symbol="KMNO",
        market_index=24,
        oracle=Pubkey.from_string("7aqj2wH1BH8XT3QQ3MWtvt3My7RAGf5Stm3vx5fiysJz"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="1KWEN-PERP",
        base_asset_symbol="1KWEN",
        market_index=25,
        oracle=Pubkey.from_string("F47c7aJgYkfKXQ9gzrJaEpsNwUKHprysregTWXrtYLFp"),
        oracle_source=OracleSource.Pyth1KPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="TRUMP-WIN-2024-PREDICT",
        base_asset_symbol="TRUMP-WIN-2024",
        market_index=26,
        oracle=Pubkey.from_string("3TVuLmEGBRfVgrmFRtYTheczXaaoRBwcHw1yibZHSeNA"),
        oracle_source=OracleSource.Prelaunch(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="KAMALA-POPULAR-VOTE-2024-PREDICT",
        base_asset_symbol="KAMALA-POPULAR-VOTE",
        market_index=27,
        oracle=Pubkey.from_string("GU6CA7a2KCyhpfqZNb36UAfc9uzKBM8jHjGdt245QhYX"),
        oracle_source=OracleSource.Prelaunch(),  # type: ignore
    ),
    # 28 sDAQaZQJQ4RXAxH3x526mbEXyQZT15ktkL84d7hmk7M RANDOM-2024-BET OracleSource.Prelaunch()
    PerpMarketConfig(
        symbol="RANDOM-2024-BET",  # Unknown!
        base_asset_symbol="RANDOM-2024",
        market_index=28,
        oracle=Pubkey.from_string("sDAQaZQJQ4RXAxH3x526mbEXyQZT15ktkL84d7hmk7M"),
        oracle_source=OracleSource.Prelaunch(),  # type: ignore
    ),
]

mainnet_perp_market_configs: list[PerpMarketConfig] = [
    PerpMarketConfig(
        symbol="SOL-PERP",
        base_asset_symbol="SOL",
        market_index=0,
        oracle=Pubkey.from_string("BAtFj4kQttZRVep3UZS2aZRDixkGYgWsbqTBVDbnSsPF"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="BTC-PERP",
        base_asset_symbol="BTC",
        market_index=1,
        oracle=Pubkey.from_string("486kr3pmFPfTsS4aZgcsQ7kS4i9rjMsYYZup6HQNSTT4"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="ETH-PERP",
        base_asset_symbol="ETH",
        market_index=2,
        oracle=Pubkey.from_string("6bEp2MiyoiiiDxcVqE8rUHQWwHirXUXtKfAEATTVqNzT"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="APT-PERP",
        base_asset_symbol="APT",
        market_index=3,
        oracle=Pubkey.from_string("79EWaCYU9jiQN8SbvVzGFAhAncUZYp3PjNg7KxmN5cLE"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="1MBONK-PERP",
        base_asset_symbol="1MBONK",
        market_index=4,
        oracle=Pubkey.from_string("GojbSnJuPdKDT1ZuHuAM5t9oz6bxTo1xhUKpTua2F72p"),
        oracle_source=OracleSource.Pyth1MPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="MATIC-PERP",
        base_asset_symbol="MATIC",
        market_index=5,
        oracle=Pubkey.from_string("BrzyDgwELy4jjjsqLQpBeUxzrsueYyMhuWpYBaUYcXvi"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="ARB-PERP",
        base_asset_symbol="ARB",
        market_index=6,
        oracle=Pubkey.from_string("8ocfAdqVRnzvfdubQaTxar4Kz5HJhNbPNmkLxswqiHUD"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="DOGE-PERP",
        base_asset_symbol="DOGE",
        market_index=7,
        oracle=Pubkey.from_string("23y63pHVwKfYSCDFdiGRaGbTYWoyr8UzhUE7zukyf6gK"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="BNB-PERP",
        base_asset_symbol="BNB",
        market_index=8,
        oracle=Pubkey.from_string("Dk8eWjuQHMbxJAwB9Sg7pXQPH4kgbg8qZGcUrWcD9gTm"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="SUI-PERP",
        base_asset_symbol="SUI",
        market_index=9,
        oracle=Pubkey.from_string("HBordkz5YxjzNURmKUY4vfEYFG9fZyZNeNF1VDLMoemT"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="1MPEPE-PERP",
        base_asset_symbol="1MPEPE",
        market_index=10,
        oracle=Pubkey.from_string("CLxofhtzvLiErpn25wvUzpZXEqBhuZ6WMEckEraxyuGt"),
        oracle_source=OracleSource.Pyth1MPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="OP-PERP",
        base_asset_symbol="OP",
        market_index=11,
        oracle=Pubkey.from_string("C9Zi2Y3Mt6Zt6pcFvobN3N29HcrzKujPAPBDDTDRcUa2"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="RNDR-PERP",
        base_asset_symbol="RNDR",
        market_index=12,
        oracle=Pubkey.from_string("8TQztfGcNjHGRusX4ejQQtPZs3Ypczt9jWF6pkgQMqUX"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="XRP-PERP",
        base_asset_symbol="XRP",
        market_index=13,
        oracle=Pubkey.from_string("9757epAjXWCWQH98kyK9vzgehd1XDVEf7joNHUaKk3iV"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="HNT-PERP",
        base_asset_symbol="HNT",
        market_index=14,
        oracle=Pubkey.from_string("9b1rcK9RUPK2vAqwNYCYEG34gUVpS2WGs2YCZZy2X5Tb"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="INJ-PERP",
        base_asset_symbol="INJ",
        market_index=15,
        oracle=Pubkey.from_string("BfXcyDWJmYADa5eZD7gySSDd6giqgjvm7xsAhQ239SUD"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="LINK-PERP",
        base_asset_symbol="LINK",
        market_index=16,
        oracle=Pubkey.from_string("Gwvob7yoLMgQRVWjScCRyQFMsgpRKrSAYisYEyjDJwEp"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="RLB-PERP",
        base_asset_symbol="RLB",
        market_index=17,
        oracle=Pubkey.from_string("4CyhPqyVK3UQHFWhEpk91Aw4WbBsN3JtyosXH6zjoRqG"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="PYTH-PERP",
        base_asset_symbol="PYTH",
        market_index=18,
        oracle=Pubkey.from_string("GqkCu7CbsPVz1H6W6AAHuReqbJckYG59TXz7Y5HDV7hr"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="TIA-PERP",
        base_asset_symbol="TIA",
        market_index=19,
        oracle=Pubkey.from_string("C6LHPUrgjrgo5eNUitC8raNEdEttfoRhmqdJ3BHVBJhi"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="JTO-PERP",
        base_asset_symbol="JTO",
        market_index=20,
        oracle=Pubkey.from_string("Ffq6ACJ17NAgaxC6ocfMzVXL3K61qxB2xHg6WUawWPfP"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="SEI-PERP",
        base_asset_symbol="SEI",
        market_index=21,
        oracle=Pubkey.from_string("EVyoxFo5jWpv1vV7p6KVjDWwVqtTqvrZ4JMFkieVkVsD"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="AVAX-PERP",
        base_asset_symbol="AVAX",
        market_index=22,
        oracle=Pubkey.from_string("FgBGHNex4urrBmNbSj8ntNQDGqeHcWewKtkvL6JE6dEX"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="WIF-PERP",
        base_asset_symbol="WIF",
        market_index=23,
        oracle=Pubkey.from_string("6x6KfE7nY2xoLCRSMPT1u83wQ5fpGXoKNBqFjrCwzsCQ"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="JUP-PERP",
        base_asset_symbol="JUP",
        market_index=24,
        oracle=Pubkey.from_string("AwqRpfJ36jnSZQykyL1jYY35mhMteeEAjh7o8LveRQin"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="DYM-PERP",
        base_asset_symbol="DYM",
        market_index=25,
        oracle=Pubkey.from_string("hnefGsC8hJi8MBajpRSkUY97wJmLoBQYXaHkz3nmw1z"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="TAO-PERP",
        base_asset_symbol="TAO",
        market_index=26,
        oracle=Pubkey.from_string("5ZPtwR9QpBLcZQVMnVURuYBmZMu1qQrBcA9Gutc5eKN3"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="W-PERP",
        base_asset_symbol="W",
        market_index=27,
        oracle=Pubkey.from_string("4HbitGsdcFbtFotmYscikQFAAKJ3nYx4t7sV7fTvsk8U"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="KMNO-PERP",
        base_asset_symbol="KMNO",
        market_index=28,
        oracle=Pubkey.from_string("7aqj2wH1BH8XT3QQ3MWtvt3My7RAGf5Stm3vx5fiysJz"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="TNSR-PERP",
        base_asset_symbol="TNSR",
        market_index=29,
        oracle=Pubkey.from_string("13jpjpVyU5hGpjsZ4HzCcmBo85wze4N8Au7U6cC3GMip"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="DRIFT-PERP",
        base_asset_symbol="DRIFT",
        market_index=30,
        oracle=Pubkey.from_string("23KmX7SNikmUr2axSCy6Zer7XPBnvmVcASALnDGqBVRR"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="CLOUD-PERP",
        base_asset_symbol="CLOUD",
        market_index=31,
        oracle=Pubkey.from_string("FNFejcXENaPgKaCTfstew9vSSvdQPnXjGTkJjUnnYvHU"),
        oracle_source=OracleSource.SwitchboardOnDemand(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="IO-PERP",
        base_asset_symbol="IO",
        market_index=32,
        oracle=Pubkey.from_string("HxM66CFwGwrvfTFFkvvA8N3CnKX6m2obzameYWDaSSdA"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="ZEX-PERP",
        base_asset_symbol="ZEX",
        market_index=33,
        oracle=Pubkey.from_string("HVwBCaR4GEB1fHrp7xCTzbYoZXL3V8b1aek2swPrmGx3"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="POPCAT-PERP",
        base_asset_symbol="POPCAT",
        market_index=34,
        oracle=Pubkey.from_string("H3pn43tkNvsG5z3qzmERguSvKoyHZvvY6VPmNrJqiW5X"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="1KWEN-PERP",
        base_asset_symbol="1KWEN",
        market_index=35,
        oracle=Pubkey.from_string("F47c7aJgYkfKXQ9gzrJaEpsNwUKHprysregTWXrtYLFp"),
        oracle_source=OracleSource.Pyth1KPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="TRUMP-WIN-2024-BET",
        base_asset_symbol="TRUMP-WIN-2024",
        market_index=36,
        oracle=Pubkey.from_string("7YrQUxmxGdbk8pvns9KcL5ojbZSL2eHj62hxRqggtEUR"),
        oracle_source=OracleSource.Prelaunch(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="KAMALA-POPULAR-VOTE-2024-BET",
        base_asset_symbol="KAMALA-POPULAR-VOTE-2024",
        market_index=37,
        oracle=Pubkey.from_string("AowFw1dCVjS8kngvTCoT3oshiUyL69k7P1uxqXwteWH4"),
        oracle_source=OracleSource.Prelaunch(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="FED-CUT-50-SEPT-2024-BET",
        base_asset_symbol="FED-CUT-50-SEPT-2024",
        market_index=38,
        oracle=Pubkey.from_string("5QzgqAbEhJ1cPnLX4tSZEXezmW7sz7PPVVg2VanGi8QQ"),
        oracle_source=OracleSource.Prelaunch(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="REPUBLICAN-POPULAR-AND-WIN-BET",
        base_asset_symbol="REPUBLICAN-POPULAR-AND-WIN",
        market_index=39,
        oracle=Pubkey.from_string("BtUUSUc9rZSzBmmKhQq4no65zHQTzMFeVYss7xcMRD53"),
        oracle_source=OracleSource.Prelaunch(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="BREAKPOINT-IGGYERIC-BET",
        base_asset_symbol="BREAKPOINT-IGGYERIC",
        market_index=40,
        oracle=Pubkey.from_string("2ftYxoSupperd4ULxy9xyS2Az38wfAe7Lm8FCAPwjjVV"),
        oracle_source=OracleSource.Prelaunch(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="DEMOCRATS-WIN-MICHIGAN-BET",
        base_asset_symbol="DEMOCRATS-WIN-MICHIGAN",
        market_index=41,
        oracle=Pubkey.from_string("8HTDLjhb2esGU5mu11v3pq3eWeFqmvKPkQNCnTTwKAyB"),
        oracle_source=OracleSource.Prelaunch(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="TON-PERP",
        base_asset_symbol="TON",
        market_index=42,
        oracle=Pubkey.from_string("BNjCXrpEqjdBnuRy2SAUgm5Pq8B73wGFwsf6RYFJiLPY"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="LANDO-F1-SGP-WIN-BET",
        base_asset_symbol="LANDO-F1-SGP-WIN",
        market_index=43,
        oracle=Pubkey.from_string("DpJz7rjTJLxxnuqrqZTUjMWtnaMFAEfZUv5ATdb9HTh1"),
        oracle_source=OracleSource.Prelaunch(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="MOTHER-PERP",
        base_asset_symbol="MOTHER",
        market_index=44,
        oracle=Pubkey.from_string("56ap2coZG7FPWUigVm9XrpQs3xuCwnwQaWtjWZcffEUG"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="MOODENG-PERP",
        base_asset_symbol="MOODENG",
        market_index=45,
        oracle=Pubkey.from_string("21gjgEcuDppthwV16J1QpFzje3vmgMp2uSzh7pJsG7ob"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="WARWICK-FIGHT-WIN-BET",
        base_asset_symbol="WARWICK-FIGHT-WIN",
        market_index=46,
        oracle=Pubkey.from_string("Dz5Nvxo1hv7Zfyu11hy8e97twLMRKk6heTWCDGXytj7N"),
        oracle_source=OracleSource.Prelaunch(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="DBR-PERP",
        base_asset_symbol="DBR",
        market_index=47,
        oracle=Pubkey.from_string("53j4mz7cQV7mAZekKbV3n2L4bY7jY6eXdgaTkWDLYxq4"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="WLF-5B-1W-BET",
        base_asset_symbol="WLF-5B-1W",
        market_index=48,
        oracle=Pubkey.from_string("7LpRfPaWR7cQqN7CMkCmZjEQpWyqso5LGuKCvDXH5ZAr"),
        oracle_source=OracleSource.Prelaunch(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="VRSTPN-WIN-F1-24-DRVRS-CHMP-BET",
        base_asset_symbol="VRSTPN-WIN-F1-24-DRVRS-CHMP",
        market_index=49,
        oracle=Pubkey.from_string("E36rvXEwysWeiToXCpWfHVADd8bzzyR4w83ZSSwxAxqG"),
        oracle_source=OracleSource.Prelaunch(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="LNDO-WIN-F1-24-US-GP-BET",
        base_asset_symbol="LNDO-WIN-F1-24-US-GP",
        market_index=50,
        oracle=Pubkey.from_string("6AVy1y9SnJECnosQaiK2uY1kcT4ZEBf1F4DMvhxgvhUo"),
        oracle_source=OracleSource.Prelaunch(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="1KMEW-PERP",
        base_asset_symbol="1KMEW",
        market_index=51,
        oracle=Pubkey.from_string("DKGwCUcwngwmgifGxnme7zVR695LCBGk2pnuksRnbhfD"),
        oracle_source=OracleSource.Pyth1KPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="MICHI-PERP",
        base_asset_symbol="MICHI",
        market_index=52,
        oracle=Pubkey.from_string("GHzvsMDMSiuyZoWhEAuM27MKFdN2Y4fA4wSDuSd6dLMA"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="GOAT-PERP",
        base_asset_symbol="GOAT",
        market_index=53,
        oracle=Pubkey.from_string("5RgXW13Kq1RgCLEsJhhchWt3W4R2XLJnd6KqgZk6dSY7"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="FWOG-PERP",
        base_asset_symbol="FWOG",
        market_index=54,
        oracle=Pubkey.from_string("5Z7uvkAsHNN6qqkQkwcKcEPYZqiMbFE9E24p7SpvfSrv"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="PNUT-PERP",
        base_asset_symbol="PNUT",
        market_index=55,
        oracle=Pubkey.from_string("5AcetMtdRHxkse2ny44NcRdsysnXu9deW7Yy5Y63qAHE"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="RAY-PERP",
        base_asset_symbol="RAY",
        market_index=56,
        oracle=Pubkey.from_string("DPvPBacXhEyA1VXF4E3EYH3h83Bynh5uP3JLeN25TWzm"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="SUPERBOWL-LIX-LIONS-BET",
        base_asset_symbol="SUPERBOWL-LIX-LIONS",
        market_index=57,
        oracle=Pubkey.from_string("GfTeKKnBxeLSB1Hm24ArjduQM4yqaAgoGgiC99gq5E2P"),
        oracle_source=OracleSource.Prelaunch(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="SUPERBOWL-LIX-CHIEFS-BET",
        base_asset_symbol="SUPERBOWL-LIX-CHIEFS",
        market_index=58,
        oracle=Pubkey.from_string("EdB17Nyu4bnEBiSEfFrwvp4VCUvtq9eDJHc6Ujys3Jwd"),
        oracle_source=OracleSource.Prelaunch(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="HYPE-PERP",
        base_asset_symbol="HYPE",
        market_index=59,
        oracle=Pubkey.from_string("Hn9JHQHKSvtnZ2xTWCgRGVNmav2TPffH7T72T6WoJ1cw"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="LTC-PERP",
        base_asset_symbol="LTC",
        market_index=60,
        oracle=Pubkey.from_string("AmjHowvVkVJApCPUiwV9CdHVFn29LiBYZQqtZQ3xMqdg"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="ME-PERP",
        base_asset_symbol="ME",
        market_index=61,
        oracle=Pubkey.from_string("FLQjrmEPGwbCKRYZ1eYM5FPccHBrCv2cN4GBu3mWfmPH"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="PENGU-PERP",
        base_asset_symbol="PENGU",
        market_index=62,
        oracle=Pubkey.from_string("7vGHChuBJyFMYBqMLXRzBmRxWdSuwEmg8RvRm3RWQsxi"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="AI16Z-PERP",
        base_asset_symbol="AI16Z",
        market_index=63,
        oracle=Pubkey.from_string("3gdGkrmBdYR7B1MRRdRVysqhZCvYvLGHonr9b7o9WVki"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="TRUMP-PERP",
        base_asset_symbol="TRUMP",
        market_index=64,
        oracle=Pubkey.from_string("AmSLxftd19EPDR9NnZDxvdStqtRW7k9zWto7FfGaz24K"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
    PerpMarketConfig(
        symbol="MELANIA-PERP",
        base_asset_symbol="MELANIA",
        market_index=65,
        oracle=Pubkey.from_string("28Zk42cxbg4MxiTewSwoedvW6MUgjoVHSTvTW7zQ7ESi"),
        oracle_source=OracleSource.PythPull(),  # type: ignore
    ),
]
