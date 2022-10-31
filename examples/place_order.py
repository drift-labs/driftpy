
#%%
%load_ext autoreload
%autoreload 2

import sys
sys.path.append('../src/')

import driftpy
print(driftpy.__path__)

from driftpy.types import User
from driftpy.constants.config import configs
from anchorpy import Provider
import json 
from anchorpy import Wallet
from solana.rpc.async_api import AsyncClient
from driftpy.clearing_house import ClearingHouse
from driftpy.accounts import *
from driftpy.constants.numeric_constants import * 
from solana.publickey import PublicKey
from dataclasses import asdict
from solana.keypair import Keypair
import asyncio
import pathlib 
from tqdm.notebook import tqdm 

#%%
# random key 
with open('../tmp.json', 'r') as f: secret = json.load(f) 
kp = Keypair.from_secret_key(bytes(secret))
print('pk:', kp.public_key)

# todo: airdrop udsc + init account for any kp
# rn do it through UI 

# %%
config = configs['devnet']
url = 'https://api.devnet.solana.com'
wallet = Wallet(kp)
connection = AsyncClient(url)
provider = Provider(connection, wallet)
ch = ClearingHouse.from_config(config, provider)

# %%
user = await get_user_account(ch.program, ch.authority)
user.spot_positions[0].scaled_balance

# %%
from driftpy.clearing_house_user import ClearingHouseUser
chu = ClearingHouseUser(ch)
collateral = await chu.get_total_collateral()
collateral / 1e6

# %%
# %%
await ch.place_order(
    OrderParams(
        OrderType.LIMIT(), 
        MarketType.PERP(),
        PositionDirection.LONG(), 
        3, 
        BASE_PRECISION, 
        10 * PRICE_PRECISION, 
        0, 
        False, 
        False, 
        False, 
        0, 
        OrderTriggerCondition.ABOVE(), 
        oracle_price_offset=0, 
        auction_duration=None, 
        time_in_force=None, 
        auction_start_price=None
    )
)

# %%


# %%
# %%
# %%
# %%
