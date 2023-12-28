# -*- coding: utf-8 -*-
"""
Created on Dec 18 05:20:15 2023
@author: NeilFTR
"""

#Works with the following pip packages:
#driftpy 0.7.6
#solana 0.30.1
#solders 0.17.0



from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

from solders.keypair import Keypair
import asyncio



from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.types import *
from driftpy.drift_client import DriftClient
from driftpy.constants.numeric_constants import BASE_PRECISION, PRICE_PRECISION
from borsh_construct.enum import _rust_enum

import socket
TIMEOUT_SEC = 120 # default timeount in seconds
socket.setdefaulttimeout(TIMEOUT_SEC)

@_rust_enum
class PostOnlyParams:
    NONE = constructor()
    TRY_POST_ONLY = constructor()
    MUST_POST_ONLY = constructor()



async def send_post_oracle_order(oracle_spread,amount):
    # We're sending an order on BTC/USD, market index 1

    #We start by setting up our private keys :
    kp = Keypair.from_bytes(bytes([12,15,52,...,...,...]))
    #Then creating a client using your favorite RPC provider (this code should work with a free Helius RPC)
    connection = AsyncClient("https://mainnet.helius-rpc.com/?api-key=XXXX")
    #Precise your public key
    pubkey = "YOUR_PUBLIC_KEY"
    #Create the drift client
    #Please note there are a lot of ways to gather live data from Drift, here, we choose to cache data
    #As precised in the account_subscription parameter
    drift_acct = DriftClient(
        connection,
        kp,
        authority=Pubkey.from_string(pubkey),
        account_subscription=AccountSubscriptionConfig("cached"),
    )
    #Add a subbaccount to the drift client
    await drift_acct.add_user(0)
    #Update cache
    await drift_acct.account_subscriber.update_cache()
    #We're gonna send an order on BTC/USD market : market_index 1
    market_index = 1
    #Retreiving existing position for this market :
    current_pos_raw = drift_acct.users[0].get_perp_position(market_index)
    if current_pos_raw is not None:
        current_pos = current_pos_raw.base_asset_amount / float(BASE_PRECISION)
    else:
        current_pos = 0
    #Now we have our existing position for this market

    #Creating the order, please note amount is in BTC
    #Also note oracle spread needs to be different from 0
    bid_order_params = OrderParams(
        order_type=OrderType.Limit(),
        market_index=market_index,
        market_type=MarketType.Perp(),
        direction=PositionDirection.Long(),
        post_only=PostOnlyParams.TRY_POST_ONLY(),
        base_asset_amount=int(amount * BASE_PRECISION),
        price=0,
        oracle_price_offset=oracle_spread*(10**6)
    )


    place_orders_ix1 = drift_acct.get_place_orders_ix([bid_order_params])
    transaction_id=await drift_acct.send_ixs([place_orders_ix1])
    print("Transaction id : ",transaction_id)

loop = asyncio.get_event_loop()
loop.run_until_complete(send_post_oracle_order(-100,0.001))
loop.close()
