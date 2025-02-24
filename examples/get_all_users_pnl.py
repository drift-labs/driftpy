import asyncio
import csv
import logging
import os
from datetime import datetime

from anchorpy.provider import Provider, Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from tqdm import tqdm

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.drift_client import DriftClient
from driftpy.drift_user import DriftUser
from driftpy.keypair import load_keypair
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import PollingConfig, UserMapConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


load_dotenv()


async def main():
    rpc = os.environ.get("MAINNET_RPC_ENDPOINT")
    private_key = os.environ.get("PRIVATE_KEY")
    kp = load_keypair(private_key)
    wallet = Wallet(kp)
    connection = AsyncClient(rpc)
    provider = Provider(connection, wallet)
    drift_client = DriftClient(
        provider.connection,
        provider.wallet,
        "mainnet",
        account_subscription=AccountSubscriptionConfig("cached"),
    )
    await drift_client.subscribe()

    usermap_config = UserMapConfig(drift_client, PollingConfig(frequency=2))
    usermap = UserMap(usermap_config)
    await usermap.subscribe()
    # make a copy of the usermap
    usermap_copy = list(usermap.user_map.keys())

    # Setup CSV output
    filename = f"pnl_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(
            [
                "User",
                "Authority",
                "Realized PnL",
                "Unrealized PnL",
                "Total PnL",
                "Total Collateral",
            ]
        )

        # Calculate PnL
        for user_pubkey in tqdm(usermap_copy):
            try:
                user_pubkey = Pubkey.from_string(user_pubkey)
                user = DriftUser(
                    drift_client,
                    user_public_key=user_pubkey,
                    account_subscription=AccountSubscriptionConfig("cached"),
                )
                authority = str(user.get_user_account().authority)
                realized_pnl = user.get_user_account().settled_perp_pnl
                unrealized_pnl = user.get_unrealized_pnl(with_funding=True)
                total_pnl = realized_pnl + unrealized_pnl
                collateral = user.get_total_collateral()

                writer.writerow(
                    [
                        str(user_pubkey),
                        authority,
                        f"{realized_pnl:.2f}",
                        f"{unrealized_pnl:.2f}",
                        f"{total_pnl:.2f}",
                        f"{collateral:.2f}",
                    ]
                )
            except Exception as e:
                logger.error(f"Error calculating PnL for {user_pubkey}: {e}")

    logger.info(f"CSV report generated: {filename}")


if __name__ == "__main__":
    asyncio.run(main())
