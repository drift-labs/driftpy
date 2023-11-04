import sys
sys.path.append('../src/')

from driftpy.constants.config import configs
from anchorpy import Provider
from anchorpy import Wallet
from solana.rpc.async_api import AsyncClient
from driftpy.drift_client import DriftClient
from driftpy.accounts import *
from solana.keypair import Keypair
from driftpy.math.positions import is_available
from driftpy.constants.numeric_constants import *

from driftpy.drift_user import User

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

    dc = DriftClient.from_config(config, provider)
    drift_user = User(dc, authority=authority, subaccount_id=subaccount, use_cache=True)
    await drift_user.set_cache()

    user = await drift_user.get_user()
    print('subaccount name:', bytes(user.name))

    from driftpy.constants.numeric_constants import QUOTE_PRECISION
    spot_collateral = await drift_user.get_spot_market_asset_value(
        None,
        include_open_orders=True,
    )
    print('spot collat:', spot_collateral/QUOTE_PRECISION)

    pnl = await drift_user.get_unrealized_pnl(False)
    print('pnl:', pnl/QUOTE_PRECISION)

    total_collateral = await drift_user.get_total_collateral()
    print('total collateral:', total_collateral)

    perp_liability = await drift_user.get_total_perp_liability(
        None, 0, True
    )
    spot_liability = await drift_user.get_spot_market_liability(
        None, None, 0, True
    )
    print(
        'perp_liability', perp_liability, 
        'spot_liability', spot_liability
    )

    perp_market = await drift_user.get_perp_market(0)
    oracle = (await drift_user.get_perp_oracle_data(perp_market)).price / PRICE_PRECISION
    print('oracle price', oracle)

    print('init leverage, main leverage:', MARGIN_PRECISION / perp_market.margin_ratio_initial, MARGIN_PRECISION / perp_market.margin_ratio_maintenance)

    liq_price = await drift_user.get_perp_liq_price(0)
    print(
        'liq price', liq_price
    )

    total_liability = await drift_user.get_margin_requirement(None)
    total_asset_value = await drift_user.get_total_collateral()
    print(
        'total_liab', total_liability, 
        'total_asset', total_asset_value
    )
    print('leverage:', (await drift_user.get_leverage()) / 10_000)
    # Putting liq_price in if to skip if there is no position
    if liq_price:
        drift_user.CACHE['perp_market_oracles'][0].price = liq_price * PRICE_PRECISION
        print('leverage (at liq price):', (await drift_user.get_leverage()) / 10_000)

    user = await drift_user.get_user()
    print('perp positions:')
    for position in user.perp_positions:
        if not is_available(position):
            print('>', position) 

    print('time taken:', time.time() - s)    
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

