import sys


sys.path.append("../src/")

from anchorpy import Wallet

from solana.rpc.async_api import AsyncClient

from solders.keypair import Keypair
from solders.pubkey import Pubkey

from driftpy.constants.config import configs
from driftpy.constants.numeric_constants import (
    QUOTE_PRECISION,
    PRICE_PRECISION,
    MARGIN_PRECISION,
)
from driftpy.drift_client import DriftClient
from driftpy.math.perp_position import is_available
from driftpy.accounts import *
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.decode.utils import decode_name
from driftpy.math.conversion import convert_to_number


async def main(
    authority,
    subaccount,
):
    authority = Pubkey.from_string(authority)

    import time

    s = time.time()

    env = "mainnet"
    config = configs[env]
    wallet = Wallet(Keypair())  # throwaway
    connection = AsyncClient(config.default_http)

    dc = DriftClient(
        connection,
        wallet,
        config,
        account_subscription=AccountSubscriptionConfig("websocket"),
    )
    drift_user = dc.get_user()

    user = drift_user.get_user_account()
    print("subaccount name:", decode_name(user.name))

    spot_collateral = drift_user.get_spot_market_asset_value(
        None,
        include_open_orders=True,
    )
    print("spot collat:", spot_collateral / QUOTE_PRECISION)

    pnl = drift_user.get_unrealized_pnl(False)
    print("pnl:", pnl / QUOTE_PRECISION)

    total_collateral = drift_user.get_total_collateral()
    print("total collateral:", total_collateral)

    perp_liability = drift_user.get_perp_market_liability()
    spot_liability = drift_user.get_spot_market_liability_value()
    print("perp_liability", perp_liability, "spot_liability", spot_liability)

    perp_market = dc.get_perp_market_account(0)
    oracle = convert_to_number(dc.get_oracle_price_data_for_perp_market(0))
    print("oracle price", oracle)

    print(
        "init leverage, main leverage:",
        MARGIN_PRECISION / perp_market.margin_ratio_initial,
        MARGIN_PRECISION / perp_market.margin_ratio_maintenance,
    )

    liq_price = drift_user.get_perp_liq_price(0)
    print("liq price", liq_price)

    total_liability = drift_user.get_margin_requirement(None)
    total_asset_value = drift_user.get_total_collateral()
    print("total_liab", total_liability, "total_asset", total_asset_value)
    print("leverage:", (drift_user.get_leverage()) / 10_000)

    user = drift_user.get_user_account()
    print("perp positions:")
    for position in user.perp_positions:
        if not is_available(position):
            print(">", position)

    print("time taken:", time.time() - s)
    print("done! :)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--pubkey", type=str, required=True)
    parser.add_argument("--subacc", type=int, required=False, default=0)
    args = parser.parse_args()

    import asyncio

    asyncio.run(main(args.pubkey, args.subacc))
