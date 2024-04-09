'''
This example demonstrates use of the `place_and_take` instruction for perp and spot markets.
1) get L3 dlob from dlob server
2) build MakerInfo[] using UserMap
3) assemble transaction
4) simulate transaction instead of sending to show end result without fighting with landing txs

Set variables in `main()` to change order params.

python3 examples/place_and_take.py
'''
import os
import sys
import asyncio
from driftpy.addresses import get_user_stats_account_public_key
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price

from driftpy.keypair import load_keypair
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import UserMapConfig, WebsocketConfig

sys.path.append("../src/")

from anchorpy import Wallet

from solders.pubkey import Pubkey

from solana.rpc.async_api import AsyncClient

from driftpy.types import MakerInfo, MarketType, OrderType, OrderParams, PositionDirection, TxParams, is_variant
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.drift_client import DriftClient
from driftpy.constants.numeric_constants import BASE_PRECISION, PRICE_PRECISION

import requests

def get_l3(market_type: str, market_index: int):
    url = f"https://dlob.drift.trade/l3?marketType={market_type}&marketIndex={market_index}"
    response = requests.get(url)
    return response.json()


async def demo_perp_place_and_take(drift_client: DriftClient, perp_market_index: int, perp_trade_direction: PositionDirection, perp_base_amount: float):
    user_account = drift_client.get_user_account()
    user_stats = drift_client.get_user_stats()
    print(f"user referrer info: {user_stats.get_referrer_info()}")
    print(f"Placing orders under authority:   {user_account.authority}")
    print(f"Placing orders under userAccount: {drift_client.get_user_account_public_key()}, subaccount_id: {user_account.sub_account_id}")

    # user map stores User account info, this is needed to get the UserStats account for makers we want to take against
    user_map = UserMap(UserMapConfig(
        drift_client,
        WebsocketConfig(),
        drift_client.connection,
        skip_initial_load=True, # will lazy load if True
    ))
    await user_map.subscribe()

    oracle_price = drift_client.get_oracle_price_data_for_perp_market(0)
    if oracle_price is None:
        raise Exception("Failed to get oracle price")
    print(f"Perp market oracle price: {oracle_price.price / PRICE_PRECISION}")

    book_side_to_take = 'bids'
    if is_variant(perp_trade_direction, 'long'):
        book_side_to_take = 'asks'

    # demonstrating passing in 3 makers, the contract will give the best price available at fill time
    # build maker info map
    perp_l3 = get_l3("perp", perp_market_index)
    maker_infos = []
    book_side = perp_l3[book_side_to_take]
    num_makers = min(3, len(book_side))
    for maker in [level['maker'] for level in book_side[:num_makers]]:
        maker_pubkey = Pubkey.from_string(maker)
        maker_user = await user_map.must_get(maker)
        maker_user_account = maker_user.get_user_account()
        maker_infos.append(MakerInfo(
            maker=maker_pubkey,
            maker_stats=get_user_stats_account_public_key(drift_client.program_id, maker_user_account.authority),
            maker_user_account=maker_user_account,
            order=None,
        ))

    print(f"simulating place_and_take_perp tx with {len(maker_infos)} makers")
    ixs = [
        set_compute_unit_limit(600_000),
        set_compute_unit_price(100_000),
        drift_client.get_place_and_take_perp_order_ix(
            OrderParams(
                order_type=OrderType.Limit(),
                base_asset_amount=int(perp_base_amount * BASE_PRECISION),
                market_type=MarketType.Perp(),
                market_index=perp_market_index,
                direction=perp_trade_direction,
                price=oracle_price.price,
            ),
            maker_infos,
            referrer_info=user_stats.get_referrer_info(), # if your UserAccount was referred, this is required.
        )
    ]
    tx = await drift_client.tx_sender.get_versioned_tx(
        ixs,
        drift_client.wallet.payer,
        [await drift_client.fetch_market_lookup_table()])
    tx_sim = await drift_client.connection.simulate_transaction(tx) # simulate because it's been hard to land a tx
    print(f"Error: {tx_sim.value.err}")
    print(f"CU used: {tx_sim.value.units_consumed}")
    print(f"logs:")
    [print(log) for log in tx_sim.value.logs]


async def demo_spot_place_and_take(drift_client: DriftClient, user_map: UserMap, spot_market_index: int, spot_trade_direction: PositionDirection, spot_base_amount: float):
    user_account = drift_client.get_user_account()
    user_stats = drift_client.get_user_stats()
    print(f"user referrer info: {user_stats.get_referrer_info()}")
    print(f"Placing orders under authority:   {user_account.authority}")
    print(f"Placing orders under userAccount: {drift_client.get_user_account_public_key()}, subaccount_id: {user_account.sub_account_id}")

    oracle_price = drift_client.get_oracle_price_data_for_spot_market(spot_market_index)
    if oracle_price is None:
        raise Exception("Failed to get oracle price")
    print(f"Spot market oracle price: {oracle_price.price / PRICE_PRECISION}")

    book_side_to_take = 'bids'
    if is_variant(spot_trade_direction, 'long'):
        book_side_to_take = 'asks'

    # demonstrating passing in 3 makers, the contract will give the best price available at fill time
    # build maker info map
    spot_l3 = get_l3("spot", spot_market_index)
    maker_infos = []
    book_side = spot_l3[book_side_to_take]
    num_makers = min(3, len(book_side))
    for maker in [level['maker'] for level in book_side[:num_makers]]:
        maker_pubkey = Pubkey.from_string(maker)
        maker_user = await user_map.must_get(maker)
        maker_user_account = maker_user.get_user_account()
        maker_infos.append(MakerInfo(
            maker=maker_pubkey,
            maker_stats=get_user_stats_account_public_key(drift_client.program_id, maker_user_account.authority),
            maker_user_account=maker_user_account,
            order=None,
        ))

    # NOTE: spot markets use corresponding mint precision, not all spot market use BASE_PRECISION like perps
    spot_market_account = drift_client.get_spot_market_account(spot_market_index)
    if spot_market_account is None:
        raise Exception("Failed to get spot market account")
    spot_precision = 10**spot_market_account.decimals
    print(f"spot precision: {spot_precision}")

    print(f"simulating place_and_take_spot tx with {len(maker_infos)} makers")
    ixs = [
        set_compute_unit_limit(600_000),
        set_compute_unit_price(100_000),
        drift_client.get_place_and_take_spot_order_ix(
            OrderParams(
                order_type=OrderType.Limit(),
                base_asset_amount=int(spot_base_amount * spot_precision),
                market_type=MarketType.Spot(),
                market_index=spot_market_index,
                direction=spot_trade_direction,
                price=oracle_price.price,
            ),
            None, # if you want to take on openbook or phoenix then need to pass in corresponding FulfillmentInfo account here
            maker_infos,
            referrer_info=user_stats.get_referrer_info(), # if your UserAccount was referred, this is required.
        )
    ]
    tx = await drift_client.tx_sender.get_versioned_tx(
        ixs,
        drift_client.wallet.payer,
        [await drift_client.fetch_market_lookup_table()])
    tx_sim = await drift_client.connection.simulate_transaction(tx) # simulate because it's been hard to land a tx
    print(f"Error: {tx_sim.value.err}")
    print(f"CU used: {tx_sim.value.units_consumed}")
    print(f"logs:")
    [print(log) for log in tx_sim.value.logs]


async def main():
    secret = os.getenv("PRIVATE_KEY")
    url = os.getenv("RPC_URL")

    sub_account_id = 2
    perp_market_index = 0 # SOL-PERP
    spot_market_index = 9 # JTO/USDC
    trade_amount_base = 0.1 # demo buying 0.1 SOL


    kp = load_keypair(secret)
    wallet = Wallet(kp)
    connection = AsyncClient(url)

    drift_client = DriftClient(
        connection,
        wallet,
        "mainnet",
        account_subscription=AccountSubscriptionConfig("websocket"),
        tx_params=TxParams(300_000, 100_000),
        active_sub_account_id=sub_account_id,
    )
    await drift_client.subscribe()

    # user map stores User account info, this is needed to get the UserStats account for makers we want to take against
    user_map = UserMap(UserMapConfig(
        drift_client,
        WebsocketConfig(),
        drift_client.connection,
        skip_initial_load=True, # will lazy load if True
    ))
    await user_map.subscribe()

    await demo_perp_place_and_take(drift_client=drift_client, user_map=user_map, perp_market_index=perp_market_index, perp_trade_direction=PositionDirection.Long(), perp_base_amount=trade_amount_base)
    print("")
    await demo_spot_place_and_take(drift_client=drift_client, user_map=user_map, spot_market_index=spot_market_index, spot_trade_direction=PositionDirection.Long(), spot_base_amount=trade_amount_base)
    print("")

if __name__ == "__main__":
    asyncio.run(main())
    print("done")