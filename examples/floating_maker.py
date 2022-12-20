import sys
import json 
sys.path.insert(0, '../src/')

import os
import json
import copy

from anchorpy import Wallet
from anchorpy import Provider
from solana.keypair import Keypair
from solana.rpc.async_api import AsyncClient

from driftpy.constants.config import configs
from driftpy.types import *
#MarketType, OrderType, OrderParams, PositionDirection, OrderTriggerCondition

from driftpy.clearing_house import ClearingHouse
from driftpy.constants.numeric_constants import BASE_PRECISION, QUOTE_PRECISION


def order_print(orders: list[OrderParams]):
    for order in orders:
        if order.price == 0:
            pricestr = '$ORACLE'
            if order.oracle_price_offset > 0:
                pricestr += ' + '+str(order.oracle_price_offset/1e6)
            else:
                pricestr += ' - '+str(abs(order.oracle_price_offset)/1e6)
        else:
            pricestr = '$' + str(order.price/1e6)

        market_str = configs['mainnet'].markets[order.market_index].symbol

        print(str(order.direction).split('.')[-1].replace('()',''), market_str, '@', pricestr)


async def main(
    keypath, 
    env, 
    url, 
    market_index,
    base_asset_amount,
    subaccount_id,
):
    with open(os.path.expanduser(keypath), 'r') as f: secret = json.load(f) 
    kp = Keypair.from_secret_key(bytes(secret))
    print('using public key:', kp.public_key, 'subaccount=', subaccount_id)
    config = configs[env]
    wallet = Wallet(kp)
    connection = AsyncClient(url)
    provider = Provider(connection, wallet)
    drift_acct = ClearingHouse.from_config(config, provider)

    default_order_params = OrderParams(
                order_type=OrderType.LIMIT(),
                market_type=MarketType.PERP(),
                direction=PositionDirection.LONG(),
                user_order_id=0,
                base_asset_amount=int(base_asset_amount * BASE_PRECISION),
                price=0,
                market_index=market_index,
                reduce_only=False,
                post_only=False,
                immediate_or_cancel=False,
                trigger_price=0,
                trigger_condition=OrderTriggerCondition.ABOVE(),
                oracle_price_offset=0,
                auction_duration=None,
                max_ts=None,
                auction_start_price=None,
                auction_end_price=None,
            )

    bid_order_params = copy.deepcopy(default_order_params)
    bid_order_params.direction = PositionDirection.LONG()
    bid_order_params.oracle_price_offset = -1
             
    ask_order_params = copy.deepcopy(default_order_params)
    ask_order_params.direction = PositionDirection.SHORT()
    ask_order_params.oracle_price_offset = 1

    order_print([bid_order_params, ask_order_params])

    await drift_acct.send_ixs(
        [
        await drift_acct.get_cancel_orders_ix(subaccount_id),
        await drift_acct.get_place_order_ix(bid_order_params),
        await drift_acct.get_place_order_ix(ask_order_params),
        ]
    )

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--keypath', type=str, required=False, default=os.environ.get('ANCHOR_WALLET'))
    parser.add_argument('--env', type=str, default='devnet')
    parser.add_argument('--amount', type=float, required=True)
    parser.add_argument('--market', type=int, required=True)
    parser.add_argument('--operation', choices=['remove', 'add', 'view', 'settle', 'cancel'], required=False)
    parser.add_argument('--subaccount', type=int, required=False, default=0)

    args = parser.parse_args()

    if args.keypath is None:
        if os.environ['ANCHOR_WALLET'] is None:
            raise NotImplementedError("need to provide keypath or set ANCHOR_WALLET")
        else:
            args.keypath = os.environ['ANCHOR_WALLET']

    if args.env == 'devnet':
        url = 'https://api.devnet.solana.com'
    elif args.env == 'mainnet':
        url = 'https://api.mainnet-beta.solana.com'
    else:
        raise NotImplementedError('only devnet/mainnet env supported')

    import asyncio
    asyncio.run(main(
        args.keypath, 
        args.env, 
        url,
        args.market, 
        args.amount,
        args.subaccount,
    ))



