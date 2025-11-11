"""
Place and take with Pyth Lazer oracle updates.
"""

import asyncio
import os
import sys

from driftpy.addresses import get_user_stats_account_public_key
from driftpy.keypair import load_keypair
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import UserMapConfig
from driftpy.user_map.user_map_config import WebsocketConfig
from solders.compute_budget import set_compute_unit_limit
from solders.compute_budget import set_compute_unit_price
from anchorpy import Context


sys.path.append("../src/")

from anchorpy import Wallet
from dotenv import load_dotenv
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.constants.numeric_constants import BASE_PRECISION
from driftpy.constants.numeric_constants import PRICE_PRECISION
from driftpy.drift_client import DriftClient
from driftpy.types import is_variant
from driftpy.types import MakerInfo
from driftpy.types import MarketType
from driftpy.types import OrderParams
from driftpy.types import OrderType
from driftpy.types import PositionDirection
from driftpy.types import TxParams
import requests
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey


load_dotenv()


# Pyth Lazer constants (replace with actual values)
PYTH_LAZER_STORAGE = Pubkey.from_string("test")
INSTRUCTIONS_SYSVAR = Pubkey.from_string("test")


def get_l3(market_type: str, market_index: int):
    url = f"https://dlob.drift.trade/l3?marketType={market_type}&marketIndex={market_index}"
    response = requests.get(url)
    return response.json()


async def demo_perp_place_and_take(drift_client: DriftClient, user_map: UserMap):
    oracle_price = drift_client.get_oracle_price_data_for_perp_market(0)
    
    # Get makers from L3 orderbook
    perp_l3 = get_l3("perp", 0)
    maker_infos = []
    for maker in [level["maker"] for level in perp_l3["asks"][:2]]:
        maker_user = await user_map.must_get(maker)
        maker_infos.append(MakerInfo(
            maker=Pubkey.from_string(maker),
            maker_stats=get_user_stats_account_public_key(drift_client.program_id, maker_user.get_user_account().authority),
            maker_user_account=maker_user.get_user_account(),
            order=None,
        ))

    # Build transaction with oracle update
    ixs = [
        set_compute_unit_limit(600_000),
        set_compute_unit_price(100_000),
        # Pyth Lazer oracle update
        drift_client.program.instruction["post_pyth_lazer_oracle_update"](
            b"",  # pyth_message
            ctx=Context(accounts={
                "keeper": drift_client.wallet.public_key,
                "pyth_lazer_storage": PYTH_LAZER_STORAGE,
                "ix_sysvar": INSTRUCTIONS_SYSVAR,
            })
        ),
        # Place and take order
        drift_client.get_place_and_take_perp_order_ix(
            OrderParams(
                order_type=OrderType.Limit(),
                base_asset_amount=int(0.1 * BASE_PRECISION),
                market_type=MarketType.Perp(),
                market_index=0,
                direction=PositionDirection.Long(),
                price=oracle_price.price,
            ),
            maker_infos,
        ),
    ]
    
    tx = await drift_client.tx_sender.get_versioned_tx(ixs, drift_client.wallet.payer, [])
    tx_sim = await drift_client.connection.simulate_transaction(tx)
    print(f"Perp simulation - Error: {tx_sim.value.err}, CU: {tx_sim.value.units_consumed}")


async def demo_spot_place_and_take(drift_client: DriftClient, user_map: UserMap):
    oracle_price = drift_client.get_oracle_price_data_for_spot_market(9)
    spot_market = drift_client.get_spot_market_account(9)
    
    # Get makers from L3 orderbook  
    spot_l3 = get_l3("spot", 9)
    maker_infos = []
    for maker in [level["maker"] for level in spot_l3["asks"][:2]]:
        maker_user = await user_map.must_get(maker)
        maker_infos.append(MakerInfo(
            maker=Pubkey.from_string(maker),
            maker_stats=get_user_stats_account_public_key(drift_client.program_id, maker_user.get_user_account().authority),
            maker_user_account=maker_user.get_user_account(),
            order=None,
        ))

    # Build transaction with oracle update
    ixs = [
        set_compute_unit_limit(600_000),
        set_compute_unit_price(100_000),
        # Pyth Lazer oracle update
        drift_client.program.instruction["post_pyth_lazer_oracle_update"](
            b"",  # pyth_message
            ctx=Context(accounts={
                "keeper": drift_client.wallet.public_key,
                "pyth_lazer_storage": PYTH_LAZER_STORAGE,
                "ix_sysvar": INSTRUCTIONS_SYSVAR,
            })
        ),
        # Place and take order
        drift_client.get_place_and_take_spot_order_ix(
            OrderParams(
                order_type=OrderType.Limit(),
                base_asset_amount=int(0.1 * 10**spot_market.decimals),
                market_type=MarketType.Spot(),
                market_index=9,
                direction=PositionDirection.Long(),
                price=oracle_price.price,
            ),
            None,
            maker_infos,
        ),
    ]
    
    tx = await drift_client.tx_sender.get_versioned_tx(ixs, drift_client.wallet.payer, [])
    tx_sim = await drift_client.connection.simulate_transaction(tx)
    print(f"Spot simulation - Error: {tx_sim.value.err}, CU: {tx_sim.value.units_consumed}")


async def main():
    kp = load_keypair(os.getenv("PRIVATE_KEY"))
    connection = AsyncClient(os.getenv("RPC_URL"))
    
    drift_client = DriftClient(connection, Wallet(kp), "mainnet")
    await drift_client.subscribe()

    user_map = UserMap(UserMapConfig(drift_client, WebsocketConfig(), connection, skip_initial_load=True))
    await user_map.subscribe()

    await demo_perp_place_and_take(drift_client, user_map)
    await demo_spot_place_and_take(drift_client, user_map)


if __name__ == "__main__":
    asyncio.run(main())
    print("done")
