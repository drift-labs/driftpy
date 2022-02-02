URL_PREPEND = "https://raw.githubusercontent.com/drift-labs/protocol-v1"
CONFIG = {
    "devnet": {
        "ENV": "devnet",
        "URL": "https://api.devnet.solana.com/",
        "IDL_URL": URL_PREPEND + "/master/sdk/src/idl/clearing_house.json",
        "PYTH_ORACLE_MAPPING_ADDRESS": "BmA9Z6FjioHJPpjT39QazZyhDRUdZy2ezwx4GiDdE2u2",
        "CLEARING_HOUSE_PROGRAM_ID": "AsW7LnXB9UA1uec9wi9MctYTgTz7YH9snhxd16GsFaGX",
        "USDC_MINT_ADDRESS": "8zGuJQqwhZafTah7Uc7Z4tXRnguqkn5KLFAP8oV6PHe2",
    },
    "devnet-limits": {
        "ENV": "devnet",
        "URL": "https://api.devnet.solana.com/",
        "IDL_URL": URL_PREPEND
        + "/crispheaney/off-chain-orders/sdk/src/idl/clearing_house.json",
        "PYTH_ORACLE_MAPPING_ADDRESS": "BmA9Z6FjioHJPpjT39QazZyhDRUdZy2ezwx4GiDdE2u2",
        "CLEARING_HOUSE_PROGRAM_ID": "HiZ8CnfEE9LrBZTfc8hBneWrPg1Cbsn8Wdy6SPLfae9V",
        "USDC_MINT_ADDRESS": "8zGuJQqwhZafTah7Uc7Z4tXRnguqkn5KLFAP8oV6PHe2",
    },
    "mainnet": {
        "ENV": "mainnet-beta",
        "URL": "https://api.mainnet-beta.solana.com/",
        # 'IDL_URL':'',
        "PYTH_ORACLE_MAPPING_ADDRESS": "AHtgzX45WTKfkPG53L6WYhGEXwQkN1BVknET3sVsLL8J",
        "CLEARING_HOUSE_PROGRAM_ID": "dammHkt7jmytvbS3nHTxQNEcP59aE57nxwV21YdqEDN",
        "USDC_MINT_ADDRESS": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    },
}
