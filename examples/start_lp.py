import sys
sys.path.append('../src/')

from driftpy.constants.config import configs
from anchorpy import Provider
import json 
from anchorpy import Wallet
from solana.rpc.async_api import AsyncClient
from driftpy.clearing_house import ClearingHouse
from driftpy.accounts import *
from solana.keypair import Keypair

# todo: airdrop udsc + init account for any kp
# rn do it through UI 
from driftpy.clearing_house_user import ClearingHouseUser
from driftpy.constants.numeric_constants import AMM_RESERVE_PRECISION
from solana.rpc import commitment
import pprint
from driftpy.constants.numeric_constants import QUOTE_PRECISION

async def view_logs(
    sig: str,
    connection: AsyncClient
):
    connection._commitment = commitment.Confirmed 
    logs = ''
    try: 
        await connection.confirm_transaction(sig, commitment.Confirmed)
        logs = (await connection.get_transaction(sig))["result"]["meta"]["logMessages"]
    finally:
        connection._commitment = commitment.Processed 
    pprint.pprint(logs)

async def main(
    keypath, 
    env, 
    url, 
    market_index,
    liquidity_amount,
    operation,
):
    with open(keypath, 'r') as f: secret = json.load(f) 
    kp = Keypair.from_secret_key(bytes(secret))
    print('using public key:', kp.public_key)
    print('market:', market_index)
    
    config = configs[env]
    wallet = Wallet(kp)
    connection = AsyncClient(url)
    provider = Provider(connection, wallet)

    ch = ClearingHouse.from_config(config, provider)
    chu = ClearingHouseUser(ch)

    total_collateral = await chu.get_total_collateral()
    print('total collateral:', total_collateral/QUOTE_PRECISION)

    if total_collateral == 0:
        print('cannot lp with 0 collateral')
        return

    market = await get_perp_market_account(
        ch.program, 
        market_index
    )
    lp_amount = liquidity_amount * AMM_RESERVE_PRECISION
    lp_amount -= lp_amount % market.amm.order_step_size
    print('standardized lp amount:', lp_amount / AMM_RESERVE_PRECISION)
    
    if lp_amount < market.amm.order_step_size:
        print('lp amount too small - exiting...')
    
    print(f'{operation}ing {lp_amount} lp shares...')

    if operation == 'add':
        resp = input('confirm adding liquidity: Y?')
        if resp != 'Y':
            print('confirmation failed exiting...')
            return
        sig = ch.add_liquidity(lp_amount, market_index)
        print(sig)

    elif operation == 'remove':
        resp = input('confirm removing liquidity: Y?')
        if resp != 'Y':
            print('confirmation failed exiting...')
            return
        sig = await ch.remove_liquidity(lp_amount, market_index)
        print(sig)

    elif operation == 'view': 
        pass

    elif operation == 'settle':
        resp = input('confirm settling revenue to if stake: Y?')
        if resp != 'Y':
            print('confirmation failed exiting...')
            return
        sig = await ch.settle_lp(ch.authority, market_index)
        print(sig)
        
    else: 
        return

    position = await ch.get_user_position(market_index)
    market = await get_perp_market_account(ch.program, market_index)
    percent_provided = (position.lp_shares  / market.amm.sqrt_k) * 100
    print(f"lp shares: {position.lp_shares}")
    print(f"providing {percent_provided}% of total market liquidity")
    print('done! :)')

if __name__ == '__main__':
    import argparse
    import os 
    parser = argparse.ArgumentParser()
    parser.add_argument('--keypath', type=str, required=False, default=os.environ.get('ANCHOR_WALLET'))
    parser.add_argument('--env', type=str, default='devnet')
    parser.add_argument('--amount', type=float, required=False)
    parser.add_argument('--market', type=int, required=True)
    parser.add_argument('--operation', choices=['remove', 'add', 'view', 'settle'], required=True)
    args = parser.parse_args()

    if args.keypath is None:
        raise NotImplementedError("need to provide keypath or set ANCHOR_WALLET")
    
    match args.env:
        case 'devnet':
            url = 'https://api.devnet.solana.com'
        case 'mainnet':
            url = 'https://api.mainnet-beta.solana.com'
        case _:
            raise NotImplementedError('only devnet/mainnet env supported')

    import asyncio
    asyncio.run(main(
        args.keypath, 
        args.env, 
        url,
        args.market, 
        args.amount
    ))

