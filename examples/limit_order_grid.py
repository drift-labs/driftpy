import os
import json
import copy
import sys
sys.path.append('../src/')

from anchorpy import Wallet
from anchorpy import Provider
from solana.keypair import Keypair
from solana.rpc.async_api import AsyncClient

from driftpy.constants.config import configs
from driftpy.types import *
#MarketType, OrderType, OrderParams, PositionDirection, OrderTriggerCondition
from driftpy.accounts import get_perp_market_account, get_spot_market_account
from driftpy.math.oracle import get_oracle_data
from driftpy.math.spot_market import get_signed_token_amount, get_token_amount
from driftpy.clearing_house import ClearingHouse
from driftpy.clearing_house_user import ClearingHouseUser
from driftpy.constants.numeric_constants import BASE_PRECISION, PRICE_PRECISION
from borsh_construct.enum import _rust_enum
import time

@_rust_enum
class PostOnlyParams:
    NONE = constructor()
    TRY_POST_ONLY = constructor()
    MUST_POST_ONLY = constructor()

def order_print(orders: list[OrderParams], market_str=None):
    for order in orders:
        if order.price == 0:
            pricestr = '$ORACLE'
            if order.oracle_price_offset > 0:
                pricestr += ' + '+str(order.oracle_price_offset/1e6)
            else:
                pricestr += ' - '+str(abs(order.oracle_price_offset)/1e6)
        else:
            pricestr = '$' + str(order.price/1e6)

        if market_str == None:
            market_str = configs['mainnet'].markets[order.market_index].symbol

        print(str(order.direction).split('.')[-1].replace('()',''), market_str, '@', pricestr)


def calculate_grid_prices(num_of_grids, upper_price, lower_price, current_price, chunk_increment=0.0):
    if upper_price is None and lower_price is None:
        # default to .5% grid around oracle
        upper_price = current_price * 1.005
        lower_price = current_price * .9995
    elif upper_price is not None and lower_price is None:
        lower_price = current_price
    elif lower_price is not None and upper_price is None:
        upper_price = current_price

    price_range = upper_price - lower_price
    grid_size = price_range / num_of_grids

    bid_prices = []
    ask_prices = []

    for i in range(num_of_grids):
        price = lower_price + (grid_size * i)
        if price < current_price and price > lower_price:
            bid_prices.append(price - chunk_increment)
        elif price > current_price and price < upper_price:
            ask_prices.append(price + chunk_increment)

    ask_prices.append(upper_price)
    reversed(bid_prices) # make it descending order

    return bid_prices, ask_prices

async def main(
    keypath, 
    env, 
    url, 
    subaccount_id,
    market_name,
    quote_asset_amount,
    grids,
    upper_price,
    lower_price,
    min_position,
    max_position,
    authority=None,
    taker=False
):
    if min_position is not None and max_position is not None:
        assert(min_position < max_position)
    with open(os.path.expanduser(keypath), 'r') as f: secret = json.load(f) 
    kp = Keypair.from_secret_key(bytes(secret))
    print('using public key:', kp.public_key, 'subaccount=', subaccount_id)
    config = configs[env]
    wallet = Wallet(kp)
    connection = AsyncClient(url)
    provider = Provider(connection, wallet)
    drift_acct = ClearingHouse.from_config(config, provider, authority=PublicKey(authority))
    chu = ClearingHouseUser(drift_acct)
    is_perp  = 'PERP' in market_name.upper()
    market_type = MarketType.PERP() if is_perp else MarketType.SPOT()

    market_index = -1
    for perp_market_config in config.markets:
        if perp_market_config.symbol == market_name:
            market_index = perp_market_config.market_index
    for spot_market_config in config.banks:
        if spot_market_config.symbol == market_name:
            market_index = spot_market_config.bank_index

    if market_index == -1:
        print('INVALID MARKET')
        return

    if is_perp:
        market = await get_perp_market_account(
                drift_acct.program, market_index
            )
        try:
            oracle_data = await get_oracle_data(connection, market.amm.oracle)
            current_price = oracle_data.price/PRICE_PRECISION
        except:
            current_price = market.amm.historical_oracle_data.last_oracle_price/PRICE_PRECISION
        # current_price = 20.00
        current_pos_raw = (await chu.get_user_position(market_index))
        if current_pos_raw is not None:
            current_pos = (current_pos_raw.base_asset_amount/float(BASE_PRECISION))
        else:
            current_pos = 0

    else:
        market = await get_spot_market_account( drift_acct.program, market_index)
        try:
            oracle_data = await get_oracle_data(connection, market.oracle)
            current_price = oracle_data.price/PRICE_PRECISION
        except:
            current_price = market.historical_oracle_data.last_oracle_price/PRICE_PRECISION

        spot_pos = await chu.get_user_spot_position(market_index)
        tokens = get_token_amount(spot_pos.scaled_balance, market, spot_pos.balance_type)
        current_pos = get_signed_token_amount(tokens, spot_pos.balance_type) / (10**market.decimals)
    
    print('grid trade for '+ market_name, 'market_index=', market_index, 'price=', current_price)
    bid_prices, ask_prices = calculate_grid_prices(grids, upper_price, lower_price, current_price)
    base_asset_amount = quote_asset_amount/current_price


    base_asset_amount_per_bid = base_asset_amount/(len(ask_prices)+len(bid_prices)+1e-6)
    base_asset_amount_per_ask = base_asset_amount/(len(ask_prices)+len(bid_prices)+1e-6)

    if min_position is not None and max_position is not None:
        available_base_asset_amount_for_bids = max(0, min(base_asset_amount, max_position - current_pos)/2)
        available_base_asset_amount_for_asks = max(0, min(base_asset_amount, current_pos - min_position)/2)

        if len(bid_prices):
            base_asset_amount_per_bid = available_base_asset_amount_for_bids/(len(bid_prices))
        if len(ask_prices):
            base_asset_amount_per_ask = available_base_asset_amount_for_asks/(len(ask_prices))
        


    default_order_params = OrderParams(
                order_type=OrderType.LIMIT(),
                market_type=market_type,
                direction=PositionDirection.LONG(),
                user_order_id=0,
                base_asset_amount=0,
                price=0,
                market_index=market_index,
                reduce_only=False,
                post_only=PostOnlyParams.TRY_POST_ONLY() if not taker else PostOnlyParams.NONE(),
                immediate_or_cancel=False,
                trigger_price=0,
                trigger_condition=OrderTriggerCondition.ABOVE(),
                oracle_price_offset=0,
                auction_duration=None,
                max_ts=None,
                auction_start_price=None,
                auction_end_price=None,
            )
    order_params = []
    for x in bid_prices:
        bid_order_params = copy.deepcopy(default_order_params)
        bid_order_params.direction = PositionDirection.LONG()
        bid_order_params.base_asset_amount = int(base_asset_amount_per_bid * BASE_PRECISION)            
        bid_order_params.price = int(x * PRICE_PRECISION)            
        if bid_order_params.base_asset_amount > 0:
            order_params.append(bid_order_params)

    for x in ask_prices:       
        ask_order_params = copy.deepcopy(default_order_params)
        ask_order_params.base_asset_amount = int(base_asset_amount_per_ask * BASE_PRECISION)            
        ask_order_params.direction = PositionDirection.SHORT()
        ask_order_params.price = int(x * PRICE_PRECISION)
        if ask_order_params.base_asset_amount > 0:
            order_params.append(ask_order_params)
    # print(order_params)
    # order_print([bid_order_params, ask_order_params], market_name)

    perp_orders_ix = []
    spot_orders_ix = []
    if is_perp:
        perp_orders_ix = await drift_acct.get_place_perp_orders_ix(order_params, subaccount_id)
    else:
        spot_orders_ix =  await drift_acct.get_place_spot_orders_ix(order_params, subaccount_id)
    # perp_orders_ix = [ await drift_acct.get_place_perp_order_ix(order_params[0], subaccount_id)]
    await drift_acct.send_ixs(
        perp_orders_ix + spot_orders_ix
    )

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--keypath', type=str, required=False, default=os.environ.get('ANCHOR_WALLET'))
    parser.add_argument('--env', type=str, default='devnet')
    parser.add_argument('--amount', type=float, required=True)
    parser.add_argument('--market', type=str, required=True)
    parser.add_argument('--min-position', type=float, required=False, default=None)
    parser.add_argument('--max-position', type=float, required=False, default=None)
    parser.add_argument('--lower-price', type=float, required=False, default=None)
    parser.add_argument('--upper-price', type=float, required=False,  default=None)
    parser.add_argument('--grids', type=int, required=True)
    parser.add_argument('--subaccount', type=int, required=False, default=0)
    parser.add_argument('--authority', type=str, required=False, default=None)
    parser.add_argument('--taker', type=bool, required=False, default=False)
    parser.add_argument('--loop', type=int, required=False, default=0)
    args = parser.parse_args()

    # assert(args.spread > 0, 'spread must be > $0')
    # assert(args.spread+args.offset < 2000, 'Invalid offset + spread (> $2000)')

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

    if args.loop > 0:
        while 1:
            asyncio.run(main(
                args.keypath, 
                args.env, 
                url,
                args.subaccount,
                args.market, 
                args.amount,
                args.grids,
                args.upper_price,
                args.lower_price,
                args.min_position,
                args.max_position,
                args.authority,
                args.taker
            ))
            time.sleep(args.loop)
    else:
        asyncio.run(main(
                args.keypath, 
                args.env, 
                url,
                args.subaccount,
                args.market, 
                args.amount,
                args.grids,
                args.upper_price,
                args.lower_price,
                args.min_position,
                args.max_position,
                args.authority,
                args.taker
            ))


