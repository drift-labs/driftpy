import sys
sys.path.append('../src/')

from driftpy.constants.config import configs
from anchorpy import Provider
from anchorpy import Wallet
from solana.rpc.async_api import AsyncClient
from driftpy.clearing_house import ClearingHouse
from driftpy.accounts import *
from solana.keypair import Keypair
from driftpy.math.positions import is_available

from driftpy.clearing_house_user import ClearingHouseUser

async def main(
    authority, 
    subaccount,
):
    authority = PublicKey(authority)

    import time 
    s = time.time()
    
    env = 'mainnet'
    config = configs[env]
    wallet = Wallet(Keypair()) # throwaway
    connection = AsyncClient(config.default_http)
    provider = Provider(connection, wallet)

    ch = ClearingHouse.from_config(config, provider)
    chu = ClearingHouseUser(ch, authority=authority, subaccount_id=subaccount, use_cache=True)
    await chu.set_cache()

    total_collateral = await chu.get_total_collateral()
    print('total collateral:', total_collateral)
    print('leverage:', await chu.get_leverage())

    user = await chu.get_user()
    print('perp positions:')
    for position in user.perp_positions:
        if not is_available(position):
            print('>', position) 

    print(time.time() - s)    
    print('done! :)')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--pubkey', type=str, required=True)
    parser.add_argument('--subacc', type=int, required=False, default=0)
    args = parser.parse_args()

    import asyncio
    asyncio.run(main(
        args.pubkey, 
        args.subacc
    ))

