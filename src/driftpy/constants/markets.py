from dataclasses import dataclass


@dataclass
class Market:
    symbol: str
    base_asset_symbol: str
    market_index: int
    devnet_pyth_oracle: str
    mainnet_pyth_oracle: str


MARKETS: list[Market] = [
    Market(
        symbol="SOL-PERP",
        base_asset_symbol="SOL",
        market_index=0,
        devnet_pyth_oracle="J83w4HKfqxwcq3BEMMkPFSppX3gqekLyLJBexebFVkix",
        mainnet_pyth_oracle="H6ARHf6YXhGYeQfUzQNGk6rDNnLBQKrenN712K4AQJEG",
    ),
    Market(
        symbol="BTC-PERP",
        base_asset_symbol="BTC",
        market_index=1,
        devnet_pyth_oracle="HovQMDrbAgAYPCmHVSrezcSmkMtXSSUsLDFANExrZh2J",
        mainnet_pyth_oracle="GVXRSBjFk6e6J3NbVPXohDJetcTjaeeuykUpbQF8UoMU",
    ),
    Market(
        symbol="ETH-PERP",
        base_asset_symbol="ETH",
        market_index=2,
        devnet_pyth_oracle="EdVCmQ9FSPcVe5YySXDPCRmc8aDQLKJ9xvYBMZPie1Vw",
        mainnet_pyth_oracle="JBu1AL4obBcCMqKBBxhpWCNUt136ijcuMZLFvTP7iWdB",
    ),
    Market(
        symbol="LUNA-PERP",
        base_asset_symbol="LUNA",
        market_index=3,
        devnet_pyth_oracle="8PugCXTAHLM9kfLSQWe2njE5pzAgUdpPk3Nx5zSm7BD3",
        mainnet_pyth_oracle="5bmWuR1dgP4avtGYMNKLuxumZTVKGgoN2BCMXWDNL9nY",
    ),
    Market(
        symbol="AVAX-PERP",
        base_asset_symbol="AVAX",
        market_index=4,
        devnet_pyth_oracle="FVb5h1VmHPfVb1RfqZckchq18GxRv4iKt8T4eVTQAqdz",
        mainnet_pyth_oracle="Ax9ujW5B9oqcv59N8m6f1BpTBq2rGeGaBcpKjC5UYsXU",
    ),
    Market(
        symbol="BNB-PERP",
        base_asset_symbol="BNB",
        market_index=5,
        devnet_pyth_oracle="GwzBgrXb4PG59zjce24SF2b9JXbLEjJJTBkmytuEZj1b",
        mainnet_pyth_oracle="4CkQJBxhU8EZ2UjhigbtdaPbpTe6mqf811fipYBFbSYN",
    ),
    Market(
        symbol="MATIC-PERP",
        base_asset_symbol="MATIC",
        market_index=6,
        devnet_pyth_oracle="FBirwuDFuRAu4iSGc7RGxN5koHB7EJM1wbCmyPuQoGur",
        mainnet_pyth_oracle="7KVswB9vkCgeM3SHP7aGDijvdRAHK8P5wi9JXViCrtYh",
    ),
    Market(
        symbol="ATOM-PERP",
        base_asset_symbol="ATOM",
        market_index=7,
        devnet_pyth_oracle="7YAze8qFUMkBnyLVdKT4TFUUFui99EwS5gfRArMcrvFk",
        mainnet_pyth_oracle="CrCpTerNqtZvqLcKqz1k13oVeXV9WkMD2zA9hBKXrsbN",
    ),
    Market(
        symbol="DOT-PERP",
        base_asset_symbol="DOT",
        market_index=8,
        devnet_pyth_oracle="4dqq5VBpN4EwYb7wyywjjfknvMKu7m78j9mKZRXTj462",
        mainnet_pyth_oracle="EcV1X1gY2yb4KXxjVQtTHTbioum2gvmPnFk4zYAt7zne",
    ),
    Market(
		symbol='ADA-PERP',
		base_asset_symbol='ADA',
		market_index=9,
		devnet_pyth_oracle='8oGTURNmSQkrBS1AQ5NjB2p8qY34UVmMA9ojrw8vnHus',
		mainnet_pyth_oracle='3pyn4svBbxJ9Wnn3RVeafyLWfzie6yC5eTig2S62v9SC',
		# launch_ts=1643084413000,
	),
	Market(
		symbol='ALGO-PERP',
		base_asset_symbol='ALGO',
		market_index=10,
		devnet_pyth_oracle='c1A946dY5NHuVda77C8XXtXytyR3wK1SCP3eA9VRfC3',
		mainnet_pyth_oracle='HqFyq1wh1xKvL7KDqqT7NJeSPdAqsDqnmBisUC2XdXAX',
		# launch_ts: 1643686767000,
    ),
]
