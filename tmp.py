#%%
%load_ext autoreload
%autoreload 2

import sys
sys.path.append('src/')

import driftpy
print(driftpy.__path__)

from driftpy.constants.config import configs
from anchorpy import Provider, WorkspaceType, workspace_fixture, Program

config = configs['devnet']
config

# %%
devnet_url = 'https://api.devnet.solana.com'
provider = Provider.readonly(devnet_url)

from driftpy.clearing_house import ClearingHouse
ch = ClearingHouse.from_config(config, provider)
ch 

# %%
from driftpy.clearing_house_user import ClearingHouseUser
from solana.publickey import PublicKey
pk = PublicKey("2zJhfetddV3J89zRrQ6o9W4KW2JbD6QYHjB7uT2VsgnG")
chu = ClearingHouseUser(
    ch, 
    pk
)

# %%
await chu.get_user_position(0)

# %%
await chu.get_unrealised_pnl()

# %%
# %%
