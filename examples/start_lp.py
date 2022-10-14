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
from solana.publickey import PublicKey
from dataclasses import asdict
from solana.keypair import Keypair
import asyncio
import pathlib 
from tqdm.notebook import tqdm 

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
from driftpy.constants.numeric_constants import AMM_RESERVE_PRECISION
await ch.add_liquidity(100_00 * AMM_RESERVE_PRECISION, 0)

# %%
user = await get_user_account(
    ch.program, 
    ch.authority
)
market = await get_perp_market_account(
    ch.program, 
    0
)

(user.positions[0].lp_shares / market.amm.sqrt_k) * 100

# %%
