# !pip install driftpy==0.6.25
#https://pypi.org/project/driftpy/
import sys
import json 
import pprint
sys.path.insert(0, '../src/')

import os
import json

from anchorpy import Wallet
from anchorpy import Provider
from solana.keypair import Keypair
from solana.rpc.async_api import AsyncClient


import driftpy
from driftpy.constants.config import configs
print(driftpy.__file__)
from driftpy.types import *
#MarketType, OrderType, OrderParams, PositionDirection, OrderTriggerCondition

from driftpy.clearing_house import ClearingHouse
# from driftpy.clearing_house_user import ClearingHouseUser
from driftpy.constants.numeric_constants import BASE_PRECISION, QUOTE_PRECISION

# keypath = os.path.expanduser('~/.config/solana/id2J.json')
# with open(keypath, 'r') as f: secret = json.load(f) 
# kp = Keypair.from_secret_key(bytes(secret))
# url = 'https://api.mainnet-beta.solana.com'
# print('using public key:', kp.public_key)
    
# ENV = 'mainnet'
# config = configs[ENV]
# wallet = Wallet(kp)
# connection = AsyncClient(url)
# provider = Provider(connection, wallet)
# drift_acct = ClearingHouse.from_config(config, provider)
# subaccount_id = 0

# market_index = 0 # SOL
# base_asset_amount = 1 * BASE_PRECISION

# default_order_params = OrderParams(
#             order_type=OrderType.LIMIT(),
#             market_type=MarketType.PERP(),
#             direction=PositionDirection.LONG(),
#             user_order_id=0,
#             base_asset_amount=base_asset_amount,
#             price=0,
#             market_index=market_index,
#             reduce_only=False,
#             post_only=False,
#             immediate_or_cancel=False,
#             trigger_price=0,
#             trigger_condition=OrderTriggerCondition.ABOVE(),
#             oracle_price_offset=0,
#             auction_duration=None,
#             max_ts=None,
#             auction_start_price=None,
#             auction_end_price=None,
#         )

# bid_order_params = default_order_params
# bid_order_params.direction = PositionDirection.LONG()
# bid_order_params.oracle_offset_price = -1
                                                   
# ask_order_params = default_order_params
# ask_order_params.direction = PositionDirection.SHORT()
# ask_order_params.oracle_offset_price = 1

# await drift_acct.send_ixs(
#     [
#     await drift_acct.get_cancel_order_ix(None, subaccount_id),
#     await drift_acct.get_place_order_ix(bid_order_params),
#     await drift_acct.get_place_order_ix(ask_order_params),
#     ]
# )
async def main(
    keypath, 
    env, 
    url, 
    market_index,
    base_asset_amount,
):
    with open(keypath, 'r') as f: secret = json.load(f) 
    kp = Keypair.from_secret_key(bytes(secret))
    print('using public key:', kp.public_key)
    print(configs.keys())
    config = configs["mainnet"]
    wallet = Wallet(kp)
    connection = AsyncClient(url)
    provider = Provider(connection, wallet)
    drift_acct = ClearingHouse.from_config(config, provider)
    subaccount_id = 0

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

    bid_order_params = default_order_params
    bid_order_params.direction = PositionDirection.LONG()
    bid_order_params.oracle_offset_price = -1
                                                    
    ask_order_params = default_order_params
    ask_order_params.direction = PositionDirection.SHORT()
    ask_order_params.oracle_offset_price = 1

    await drift_acct.send_ixs(
        [
        await drift_acct.get_cancel_order_ix(None, subaccount_id),
        await drift_acct.get_place_order_ix(bid_order_params),
        await drift_acct.get_place_order_ix(ask_order_params),
        ]
    )

if __name__ == '__main__':
    import argparse
    import os 
    parser = argparse.ArgumentParser()
    parser.add_argument('--keypath', type=str, required=False, default=os.environ.get('ANCHOR_WALLET'))
    parser.add_argument('--env', type=str, default='devnet')
    parser.add_argument('--amount', type=float, required=True)
    parser.add_argument('--market', type=int, required=True)
    parser.add_argument('--operation', choices=['remove', 'add', 'view', 'settle', 'cancel'], required=False)

    args = parser.parse_args()

    # if args.operation == 'add':
    #     assert args.amount is not None, 'adding requires --amount'
    
    # if args.operation == 'remove' and args.amount is None:
    #     print('removing full IF stake')

    if args.keypath is None:
        args.keypath = os.path.expanduser('~/.config/solana/id2J.json')
        # raise NotImplementedError("need to provide keypath or set ANCHOR_WALLET")

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
        # args.operation,
    ))



