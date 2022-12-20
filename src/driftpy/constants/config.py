from driftpy.constants.banks import devnet_banks, mainnet_banks, Bank
from driftpy.constants.markets import devnet_markets, mainnet_markets, Market
from dataclasses import dataclass
from solana.publickey import PublicKey


@dataclass
class Config:
    env: str
    pyth_oracle_mapping_address: PublicKey
    clearing_house_program_id: PublicKey
    usdc_mint_address: PublicKey
    default_http: str 
    default_ws: str
    markets: list[Market]
    banks: list[Bank]


configs = {
    "devnet": Config(
        env='devnet',
        pyth_oracle_mapping_address=PublicKey('BmA9Z6FjioHJPpjT39QazZyhDRUdZy2ezwx4GiDdE2u2'),
		clearing_house_program_id=PublicKey('dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH'),
		usdc_mint_address=PublicKey('8zGuJQqwhZafTah7Uc7Z4tXRnguqkn5KLFAP8oV6PHe2'),
        default_http='https://api.devnet.solana.com',
        default_ws='wss://api.devnet.solana.com',
		markets=devnet_markets,
		banks=devnet_banks,
    ), 
    "mainnet": Config(
        env='mainnet',
        pyth_oracle_mapping_address=PublicKey('AHtgzX45WTKfkPG53L6WYhGEXwQkN1BVknET3sVsLL8J'),
		clearing_house_program_id=PublicKey('dRiftyHA39MWEi3m9aunc5MzRF1JYuBsbn6VPcn33UH'),
		usdc_mint_address=PublicKey('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'),
        default_http='https://api.mainnet-beta.solana.com',
        default_ws='wss://api.mainnet-beta.solana.com',
        markets=mainnet_markets, 
        banks=mainnet_banks
    )
}
