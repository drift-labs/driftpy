import asyncio
import os
import time

import dotenv
from anchorpy import Wallet
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.constants.numeric_constants import (
    MARGIN_PRECISION,
    QUOTE_PRECISION,
)
from driftpy.decode.utils import decode_name
from driftpy.drift_client import DriftClient
from driftpy.keypair import load_keypair
from driftpy.math.conversion import convert_to_number
from driftpy.math.perp_position import is_available

dotenv.load_dotenv()


async def main():
    s = time.time()
    kp = load_keypair(os.getenv("PRIVATE_KEY"))
    wallet = Wallet(kp)
    connection = AsyncClient(os.getenv("RPC_URL"))
    dc = DriftClient(
        connection,
        wallet,
        account_subscription=AccountSubscriptionConfig("websocket"),
    )
    await dc.subscribe()
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

    perp_liability = drift_user.get_total_perp_position_liability()
    spot_liability = drift_user.get_spot_market_liability_value()
    print("perp_liability", perp_liability, "spot_liability", spot_liability)

    perp_market = dc.get_perp_market_account(0)
    oracle = convert_to_number(
        dc.get_oracle_price_data_for_perp_market(0).price, QUOTE_PRECISION
    )
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
    orders = drift_user.get_open_orders()
    print("orders:", orders)
    print("done! :)")


if __name__ == "__main__":
    asyncio.run(main())
