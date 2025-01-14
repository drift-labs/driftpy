import asyncio
import logging
import os

import dotenv
from anchorpy.provider import Wallet
from solana.rpc.async_api import AsyncClient
from solana.rpc.core import RPCException

from driftpy.accounts.get_accounts import get_protected_maker_mode_stats
from driftpy.constants.numeric_constants import BASE_PRECISION, PRICE_PRECISION
from driftpy.constants.perp_markets import mainnet_perp_market_configs
from driftpy.drift_client import DriftClient
from driftpy.keypair import load_keypair
from driftpy.math.user_status import is_user_protected_maker
from driftpy.types import (
    MarketType,
    OrderParams,
    OrderType,
    PositionDirection,
    TxParams,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


async def get_drift_client() -> DriftClient:
    dotenv.load_dotenv()
    rpc_url = os.getenv("RPC_TRITON")
    private_key = os.getenv("PRIVATE_KEY")
    if not rpc_url or not private_key:
        raise Exception("Missing env vars")
    kp = load_keypair(private_key)
    drift_client = DriftClient(
        connection=AsyncClient(rpc_url),
        wallet=Wallet(kp),
        env="mainnet",
        tx_params=TxParams(700_000, 10_000),
    )
    await drift_client.subscribe()
    logger.info("Drift client subscribed")

    user = drift_client.get_user()
    is_protected_maker = is_user_protected_maker(user.get_user_account())
    if not is_protected_maker:
        logger.warning("User is not a protected maker")
        logger.warning("Attempting to make protected maker...")
        stats = await get_protected_maker_mode_stats(drift_client.program)
        logger.info(f"Protected maker stats: {stats}")
        if stats["current_users"] >= stats["max_users"]:
            logger.error("No room for a new protected maker")
            print("---\nYour orders will not be protected. Continue anyway? (Y/n)")
            if input().lower().startswith("n"):
                exit(1)
            return drift_client

        try:
            result = await drift_client.update_user_protected_maker_orders(0, True)
            logger.info(result)
        except RPCException as e:
            logger.error(f"Failed to make protected maker: {e}")
            print("---\nYour orders will not be protected. Continue anyway? (Y/n)")
            if input().lower().startswith("n"):
                exit(1)

    logger.info("Drift client is ready.")

    return drift_client


class OracleMaker:
    def __init__(self, drift_client: DriftClient, targets: dict[str, dict[str, float]]):
        self.client = drift_client
        self.last_positions: dict[int, float] = {}
        self.target_positions = {
            symbol_to_market_index(k): v for k, v in targets.items()
        }
        logger.info(f"OracleMaker initialized with targets: {self.target_positions}")

    def get_orders_for_market(self, market_index: int, spread: float):
        pos = self.client.get_perp_position(market_index)
        current_pos = pos.base_asset_amount / BASE_PRECISION if pos else 0.0
        target_position = self.target_positions[market_index]["target"] or 0.0
        pos_diff = abs(current_pos - target_position)
        t = min(1.0, pos_diff / 2.0)
        spread *= 1.0 + t  # range: [spread..2*spread]

        base_size = int(self.target_positions[market_index]["size"] * BASE_PRECISION)
        offset_iu = int(spread * PRICE_PRECISION)
        logger.info(f"Market={market_index}, current_pos={current_pos:.4f}")
        logger.info(f"Spread: {spread:.5f} base_size: {base_size} offset: {offset_iu}")

        bid = OrderParams(
            order_type=OrderType.Oracle(),  # type: ignore
            market_type=MarketType.Perp(),  # type: ignore
            direction=PositionDirection.Long(),  # type: ignore
            base_asset_amount=base_size,
            market_index=market_index,
            oracle_price_offset=-offset_iu,
        )
        ask = OrderParams(
            order_type=OrderType.Oracle(),  # type: ignore
            market_type=MarketType.Perp(),  # type: ignore
            direction=PositionDirection.Short(),  # type: ignore
            base_asset_amount=base_size,
            market_index=market_index,
            oracle_price_offset=offset_iu,
        )

        if current_pos > target_position:
            logger.info("Skipping bid order - position above target")
            bid = None
        if current_pos < -target_position:
            logger.info("Skipping ask order - position below -target")
            ask = None

        orders = [o for o in [bid, ask] if o]
        name = mainnet_perp_market_configs[market_index].symbol
        logger.info(f"Market {name}: Will place {len(orders)} orders")
        return orders

    async def place_orders_for_all_markets(self, spread: float):
        all_orders = []
        for m_idx in self.target_positions.keys():
            all_orders.extend(self.get_orders_for_market(m_idx, spread))

        await self.client.cancel_and_place_orders(
            cancel_params=(None, None, None), place_order_params=all_orders
        )


def symbol_to_market_index(symbol):
    return next(
        m.market_index for m in mainnet_perp_market_configs if m.symbol == symbol
    )


async def main():
    logger.info("Starting OracleMaker")
    drift_client = await get_drift_client()
    target_sizes_map = {
        "SOL-PERP": {"target": 2.0, "size": 2.0},
        "DRIFT-PERP": {"target": 20.0, "size": 20.0},
    }  # add as many market indexes as you want to make for
    maker = OracleMaker(drift_client, targets=target_sizes_map)
    try:
        while True:
            await maker.place_orders_for_all_markets(spread=0.008)
            await asyncio.sleep(10)
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Exiting loop...")
    finally:
        await maker.client.unsubscribe()
        logger.info("Unsubscribed from Drift client.")


if __name__ == "__main__":
    asyncio.run(main())
