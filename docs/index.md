# Drift-v2 Python SDK

<div align="center">
    <img src="docs/../img/drift.png" width="30%" height="30%">
</div>

DriftPy is the Python SDK for [Drift-v2](https://www.drift.trade/) on Solana. 
It allows you to trade and fetch data from Drift using Python.

## Installation

```
pip install driftpy
```

Note: requires Python >= 3.10.

## Key Components

- `ClearingHouse` / `clearing_house.py`: Used to interact with the protocol (deposit, withdraw, trade, lp, etc.)
- `ClearingHouseUser` / `clearing_house_user.py`: Used to fetch data from the protocol and view user metrics (leverage, free collateral, etc.)
- `accounts.py`: Used to retrieve specific on-chain accounts (State, PerpMarket, SpotMarket, etc.)
- `addresses.py`: Used to derive on-chain addresses of the accounts (publickey of the sol-market)


## Example 

```python 

from solana.keypair import Keypair
from driftpy.clearing_house import ClearingHouse 
from driftpy.clearing_house_user import ClearingHouseUser
from driftpy.constants.numeric_constants import BASE_PRECISION, AMM_RESERVE_PRECISION 

from anchorpy import Provider, Wallet
from solana.rpc.async_api import AsyncClient

# load keypair from file 
KEYPATH = '../your-keypair-secret.json'
with open(KEYPATH, 'r') as f: 
    secret = json.load(f) 
kp = Keypair.from_secret_key(bytes(secret))

# create clearing house for mainnet 
ENV = 'mainnet' 
config = configs[ENV]
wallet = Wallet(kp)
connection = AsyncClient(config.default_http)
provider = Provider(connection, wallet)

clearing_house = ClearingHouse.from_config(config, provider)
clearing_house_user = ClearingHouseUser(clearing_house)

# open a 10 SOL long position
sig = await clearing_house.open_position(
    PositionDirection.LONG(), # long
    int(10 * BASE_PRECISION), # 10 in base precision
    0, # sol market index
) 

# mint 100 LP shares on the SOL market
await clearing_house.add_liquidity(
    int(100 * AMM_RESERVE_PRECISION), 
    0, 
)

# inspect user's leverage 
leverage = await clearing_house_user.get_leverage()
print('current leverage:', leverage / 10_000)

# you can also inspect other accounts information using the (authority=) flag
bigz_chu = ClearingHouseUser(clearing_house, authority=PublicKey('bigZ'))
leverage = await bigz_chu.get_leverage()
print('bigZs leverage:', leverage / 10_000)

# clearing house user calls can be expensive on the rpc so we can cache them 
clearing_house_user = ClearingHouseUser(clearing_house, use_cache=True)
await clearing_house_user.set_cache()

# works without any rpc calls (uses the cached data)
upnl = await chu.get_unrealized_pnl(with_funding=True)
print('upnl:', upnl)
```