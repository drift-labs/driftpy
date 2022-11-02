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

    from spl.token.instructions import get_associated_token_address
    usdc_market = await get_spot_market_account(ch.program, 0)
    usdc_mint = usdc_market.mint

    ata = get_associated_token_address(wallet.public_key, usdc_mint)
    ch.usdc_ata = ata
    balance = await connection.get_token_account_balance(ata)
    print('balance', balance['result']['uiAmount'])

    from driftpy.constants.numeric_constants import QUOTE_PRECISION
    ix2 = await ch.add_insurance_fund_stake(0, 100 * QUOTE_PRECISION)

    print('done! :)')

if __name__ == '__main__':
    import argparse
    import os 
    parser = argparse.ArgumentParser()
    parser.add_argument('--keypath', type=str, required=False, default=os.environ.get('ANCHOR_WALLET'))
    parser.add_argument('--env', type=str, default='devnet')
    parser.add_argument('--amount', type=int, required=True)
    parser.add_argument('--market', type=int, required=True)
    args = parser.parse_args()

    if args.keypath is None:
        raise NotImplementedError("need to provide keypath or set ANCHOR_WALLET")

    match args.env:
        case 'devnet':
            url = 'https://api.devnet.solana.com'
        case _:
            raise NotImplementedError('only devnet env supported')

    import asyncio
    asyncio.run(main(
        args.keypath, 
        args.env, 
        url,
        args.market, 
        args.amount
    ))



