import asyncio
import os
import time
from pprint import pprint

import dotenv
from anchorpy import Wallet
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.constants.numeric_constants import (
    MARGIN_PRECISION,
    QUOTE_PRECISION,
)
from driftpy.decode.utils import decode_name
from driftpy.drift_client import DriftClient
from driftpy.drift_user import DriftUser
from driftpy.keypair import load_keypair
from driftpy.math.conversion import convert_to_number
from driftpy.math.perp_position import is_available

dotenv.load_dotenv()


async def main():
    s = time.time()
    kp = load_keypair(os.getenv("PRIVATE_KEY"))
    wallet = Wallet(kp)
    connection = AsyncClient(os.getenv("RPC_TRITON"))
    dc = DriftClient(
        connection,
        wallet,
        account_subscription=AccountSubscriptionConfig("websocket"),
    )
    await dc.subscribe()
    drift_user = dc.get_user()
    user = drift_user.get_user_account()
    print("\n=== User Info ===")
    print(f"Subaccount name: {decode_name(user.name)}")

    spot_collateral = drift_user.get_spot_market_asset_value(
        None,
        include_open_orders=True,
    )
    print("\n=== Collateral & PnL ===")
    print(f"Spot collateral: ${spot_collateral / QUOTE_PRECISION:,.2f}")

    pnl = drift_user.get_unrealized_pnl(False)
    print(f"Unrealized PnL: ${pnl / QUOTE_PRECISION:,.2f}")

    total_collateral = drift_user.get_total_collateral()
    print(f"Total collateral: ${total_collateral / QUOTE_PRECISION:,.2f}")

    perp_liability = drift_user.get_total_perp_position_liability()
    spot_liability = drift_user.get_spot_market_liability_value()
    print("\n=== Liabilities ===")
    print(f"Perp liability: ${perp_liability / QUOTE_PRECISION:,.2f}")
    print(f"Spot liability: ${spot_liability / QUOTE_PRECISION:,.2f}")

    perp_market = dc.get_perp_market_account(0)
    oracle = convert_to_number(
        dc.get_oracle_price_data_for_perp_market(0).price, QUOTE_PRECISION
    )
    print("\n=== Market Info ===")
    print(f"Oracle price: ${oracle:,.2f}")

    init_leverage = MARGIN_PRECISION / perp_market.margin_ratio_initial
    maint_leverage = MARGIN_PRECISION / perp_market.margin_ratio_maintenance
    print(f"Initial leverage: {init_leverage:.2f}x")
    print(f"Maintenance leverage: {maint_leverage:.2f}x")

    liq_price = drift_user.get_perp_liq_price(0)
    print(f"Liquidation price: ${liq_price:,.2f}")

    total_liability = drift_user.get_margin_requirement(None)
    total_asset_value = drift_user.get_total_collateral()
    print("\n=== Risk Metrics ===")
    print(f"Total liability: ${total_liability / QUOTE_PRECISION:,.2f}")
    print(f"Total asset value: ${total_asset_value / QUOTE_PRECISION:,.2f}")
    print(f"Current leverage: {(drift_user.get_leverage()) / 10_000:.2f}x")

    user = drift_user.get_user_account()
    print("\n=== Perp Positions ===")
    for position in user.perp_positions:
        if not is_available(position):
            pprint(position)

    print(f"\nTime taken: {time.time() - s:.2f}s")

    orders = drift_user.get_open_orders()
    print("\n=== Orders ===")
    pprint(orders, indent=2, width=80)

    print("\n=== Health Components ===")
    pprint(drift_user.get_health_components(), indent=2, width=80)

    # Another user
    drift_user2 = DriftUser(
        drift_client=dc,
        user_public_key=Pubkey.from_string(os.getenv("RANDOM_USER_ACCOUNT_PUBKEY")),
    )
    await drift_user2.subscribe()

    print("\n=== Perp Positions (User 2) ===")
    for position in drift_user2.get_user_account().perp_positions:
        if position.base_asset_amount != 0:
            pprint(position)

    pnl = drift_user2.get_net_usd_value()
    print(f"Net USD Value: ${pnl / QUOTE_PRECISION:,.2f}")


if __name__ == "__main__":
    asyncio.run(main())
