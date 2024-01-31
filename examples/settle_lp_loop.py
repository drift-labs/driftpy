# %%
# %load_ext autoreload
# %autoreload 2

import sys
import json
import asyncio
import pandas as pd

sys.path.append("src/")

from dataclasses import asdict

from anchorpy import Wallet

from solders.pubkey import Pubkey  # type: ignore
from solders.keypair import Keypair  # type: ignore

from solana.rpc.async_api import AsyncClient

from driftpy.constants.config import configs
from driftpy.drift_client import DriftClient
from driftpy.accounts import get_user_account, get_perp_market_account
from driftpy.account_subscription_config import AccountSubscriptionConfig


async def main():
    global summary_data

    with open("tmp.json", "r") as f:
        secret = json.load(f)
    kp = Keypair.from_secret_key(bytes(secret))
    print("pk:", kp.public_key)

    config = configs["devnet"]
    url = "https://api.devnet.solana.com"
    wallet = Wallet(kp)
    connection = AsyncClient(url)
    dc = DriftClient(
        connection,
        wallet,
        config,
        account_subscription=AccountSubscriptionConfig("websocket"),
    )
    settle_pk = Pubkey("CkZLqWuzgE985Y9RC6pt7LYvCUjN4HVXuJESt8yG7wW4")

    while True:
        print("settling...")
        await dc.settle_lp(settle_pk, 0)
        user = await get_user_account(
            dc.program,
            settle_pk,
        )
        market = await get_perp_market_account(dc.program, 0)
        position = user.positions[0]
        print("position:", position)
        print("lp position:", market.amm.market_position_per_lp)

        summary_data.append(asdict(position))

        await asyncio.sleep(10)
        print()


summary_data = []
try:
    asyncio.run(main())
finally:
    df = pd.DataFrame(summary_data)
    df.to_csv("examples/lp_summary_bot.csv", index=False)

# %%
# %%
# %%
# from driftpy.constants.numeric_constants import AMM_RESERVE_PRECISION
# n_tokens = 1_000 * AMM_RESERVE_PRECISION
# sig = await dc.add_liquidity(
#     n_tokens, 0
# )
# sig

# #%%
# import time

# %%
# %%
# # %%
# pk = Pubkey("2zJhfetddV3J89zRrQ6o9W4KW2JbD6QYHjB7uT2VsgnG")
# drift_user = User(
#     dc,
#     pk
# )

# %%
# %%
