from dataclasses import dataclass
from solana.publickey import PublicKey


@dataclass
class Market:
    symbol: str
    base_asset_symbol: str
    market_index: int
    pyth_oracle: PublicKey


devnet_markets: list[Market] = [
    Market(
        base_asset_symbol="SOL",
        symbol="SOL-PERP",
        market_index=0,
        pyth_oracle=PublicKey("J83w4HKfqxwcq3BEMMkPFSppX3gqekLyLJBexebFVkix"),
    ),
    Market(
        base_asset_symbol="BTC",
        symbol="BTC-PERP",
        market_index=1,
        pyth_oracle=PublicKey("HovQMDrbAgAYPCmHVSrezcSmkMtXSSUsLDFANExrZh2J"),
    ),
    Market(
        base_asset_symbol="ETH",
        symbol="ETH-PERP",
        market_index=2,
        pyth_oracle=PublicKey("EdVCmQ9FSPcVe5YySXDPCRmc8aDQLKJ9xvYBMZPie1Vw"),
    ),
    Market(
		symbol= 'APT-PERP',
		base_asset_symbol='APT',
		marketIndex=3,
		pyth_oracle=PublicKey('5d2QJ6u2NveZufmJ4noHja5EHs3Bv1DUMPLG5xfasSVs'),
    ),
    Market(symbol='1MBONK-PERP', base_asset_symbol='1MBONK', marketIndex=4, pyth_oracle=PublicKey('6bquU99ktV1VRiHDr8gMhDFt3kMfhCQo5nfNrg2Urvsn')),
    Market(symbol='MATIC-PERP', base_asset_symbol='MATIC', marketIndex=5, pyth_oracle=PublicKey('FBirwuDFuRAu4iSGc7RGxN5koHB7EJM1wbCmyPuQoGur')),
    Market(symbol='ARB-PERP', base_asset_symbol='ARB', marketIndex=6, pyth_oracle=PublicKey('4mRGHzjGerQNWKXyQAmr9kWqb9saPPHKqo1xziXGQ5Dh')),
    Market(symbol='DOGE-PERP', base_asset_symbol='DOGE', marketIndex=7, pyth_oracle=PublicKey('4L6YhY8VvUgmqG5MvJkUJATtzB2rFqdrJwQCmFLv4Jzy')),
    Market(symbol='BNB-PERP', base_asset_symbol='BNB', marketIndex=8, pyth_oracle=PublicKey('GwzBgrXb4PG59zjce24SF2b9JXbLEjJJTBkmytuEZj1b')),
    Market(symbol='SUI-PERP', base_asset_symbol='SUI', marketIndex=9, pyth_oracle=PublicKey('6SK9vS8eMSSj3LUX2dPku93CrNv8xLCp9ng39F39h7A5')),
    Market(symbol='1MPEPE-PERP', base_asset_symbol='1MPEPE', marketIndex=10, pyth_oracle=PublicKey('Gz9RfgDeAFSsH7BHDGyNTgCik74rjNwsodJpsCizzmkj')),
]

mainnet_markets: list[Market] = [
    Market(symbol='SOL-PERP', base_asset_symbol='SOL', marketIndex=0, pyth_oracle=PublicKey('H6ARHf6YXhGYeQfUzQNGk6rDNnLBQKrenN712K4AQJEG')),
Market(symbol='BTC-PERP', base_asset_symbol='BTC', marketIndex=1, pyth_oracle=PublicKey('GVXRSBjFk6e6J3NbVPXohDJetcTjaeeuykUpbQF8UoMU')),
Market(symbol='ETH-PERP', base_asset_symbol='ETH', marketIndex=2, pyth_oracle=PublicKey('JBu1AL4obBcCMqKBBxhpWCNUt136ijcuMZLFvTP7iWdB')),
Market(symbol='APT-PERP', base_asset_symbol='APT', marketIndex=3, pyth_oracle=PublicKey('FNNvb1AFDnDVPkocEri8mWbJ1952HQZtFLuwPiUjSJQ')),
Market(symbol='1MBONK', base_asset_symbol='1MBONK', marketIndex=4, pyth_oracle=PublicKey('8ihFLu5FimgTQ1Unh4dVyEHUGodJ5gJQCrQf4KUVB9bN')),
Market(symbol='MATIC-PERP', base_asset_symbol='MATIC', marketIndex=5, pyth_oracle=PublicKey('7KVswB9vkCgeM3SHP7aGDijvdRAHK8P5wi9JXViCrtYh')),
Market(symbol='ARB-PERP', base_asset_symbol='ARB', marketIndex=6, pyth_oracle=PublicKey('5HRrdmghsnU3i2u5StaKaydS7eq3vnKVKwXMzCNKsc4C')),
Market(symbol='DOGE-PERP', base_asset_symbol='DOGE', marketIndex=7, pyth_oracle=PublicKey('FsSM3s38PX9K7Dn6eGzuE29S2Dsk1Sss1baytTQdCaQj')),
Market(symbol='BNB-PERP', base_asset_symbol='BNB', marketIndex=8, pyth_oracle=PublicKey('4CkQJBxhU8EZ2UjhigbtdaPbpTe6mqf811fipYBFbSYN')),
Market(symbol='SUI-PERP', base_asset_symbol='SUI', marketIndex=9, pyth_oracle=PublicKey('3Qub3HaAJaa2xNY7SUqPKd3vVwTqDfDDkEUMPjXD2c1q')),
Market(symbol='1MPEPE-PERP', base_asset_symbol='1MPEPE', marketIndex=10, pyth_oracle=PublicKey('FSfxunDmjjbDV2QxpyxFCAPKmYJHSLnLuvQXDLkMzLBm')),
]
