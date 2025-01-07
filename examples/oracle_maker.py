import asyncio
import os
import signal
from logging import INFO, basicConfig, getLogger

from anchorpy.provider import Wallet
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Processed
from solana.rpc.types import TxOpts

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.constants.numeric_constants import BASE_PRECISION, PRICE_PRECISION
from driftpy.drift_client import DriftClient
from driftpy.keypair import load_keypair
from driftpy.math.user_status import is_user_protected_maker
from driftpy.tx.fast_tx_sender import FastTxSender
from driftpy.types import (
    GrpcConfig,
    MarketType,
    OrderParams,
    OrderType,
    PositionDirection,
    TxParams,
)

basicConfig(level=INFO)
logger = getLogger(__name__)

load_dotenv()


async def get_drift_client() -> DriftClient:
    rpc_url = os.getenv("RPC_TRITON")
    rpc_fqdn = os.getenv("RPC_FQDN")
    x_token = os.getenv("X_TOKEN")
    private_key = os.getenv("PRIVATE_KEY")
    if not rpc_url or not rpc_fqdn or not x_token or not private_key:
        raise Exception("Environment variables are not properly set.")

    logger.info("Initializing Drift client...")
    kp = load_keypair(private_key)
    wallet = Wallet(kp)

    connection = AsyncClient(rpc_url)
    commitment = Processed
    tx_opts = TxOpts(skip_confirmation=False, preflight_commitment=commitment)

    fast_tx_sender = FastTxSender(connection, tx_opts, 3)

    drift_client = DriftClient(
        connection=connection,
        wallet=wallet,
        env="mainnet",
        account_subscription=AccountSubscriptionConfig(
            "grpc",
            grpc_config=GrpcConfig(endpoint=rpc_fqdn, token=x_token),
        ),
        tx_params=TxParams(700_000, 50_000),  # Adjust as needed
        opts=tx_opts,
        tx_sender=fast_tx_sender,
    )

    logger.info("Subscribing to Drift client...")
    await drift_client.subscribe()
    # small delay to allow grpc data to populate
    await asyncio.sleep(10)
    user = drift_client.get_user()
    is_protected_maker = is_user_protected_maker(user.get_user_account())
    if not is_protected_maker:
        print("===> User is not a protected maker")
        print("Continue? (y/n)")
        if input() == "n":
            raise Exception("User is not a protected maker")
    logger.info("Drift client is ready.")

    return drift_client


class OracleMaker:
    """
    Places bid/ask orders around the oracle price with optional inventory mgmt
    and dynamic spread adjustments.
    """

    def __init__(
        self,
        drift_client: DriftClient,
        market_index: int,
        target_position: float = 0.0,
        max_inventory: float = 5.0,
        base_order_size: float = 1.0,
        base_spread: float = 0.01,
        float_tolerance: float = 1e-9,
    ):
        """
        :param drift_client: The Drift client for RPC calls.
        :param market_index: Market index to place orders on.
        :param target_position: Target net position (in base assets).
        :param max_inventory: Maximum net position allowed (in base assets).
        :param base_order_size: Default order size (in base assets).
        :param base_spread: Default spread as a decimal (e.g. 0.01 for 1%).
        :param float_tolerance: If values change by less than this, consider them "unchanged".
        """
        self.drift_client = drift_client
        self.market_index = market_index
        self.target_position = target_position
        self.max_inventory = max_inventory
        self.base_order_size = base_order_size
        self.base_spread = base_spread
        self.float_tolerance = float_tolerance

        self.prev_net_position = None
        self.prev_spread = None
        self.prev_order_size = None

    async def cancel_existing_orders(self):
        try:
            logger.info("Cancelling existing orders...")
            await self.drift_client.cancel_orders()
        except Exception as e:
            logger.error(f"Failed to cancel orders: {str(e)}")
            raise

    def get_net_position(self) -> float:
        """
        Fetch the user's current net position for self.market_index (in base assets).
        If no position exists, net size is 0.0.
        """
        position = self.drift_client.get_perp_position(self.market_index)
        if position is None:
            return 0.0
        return position.base_asset_amount / BASE_PRECISION

    def calculate_spread(self, current_position: float) -> float:
        """
        Dynamically adjust spread based on your net position.
        Example logic:
         - If we exceed max inventory, widen the spread drastically
         - If we are near target_position, use base_spread
        You can customize this formula or logic as needed.
        """
        position_diff = abs(current_position - self.target_position)

        if position_diff >= self.max_inventory:
            return self.base_spread * 3.0
        else:
            factor = 1.0 + (position_diff / self.max_inventory)
            return self.base_spread * factor

    def calculate_order_size(self, current_position: float) -> float:
        """
        Dynamically adjust order size. For example:
         - If net position is positive (long), we might want to reduce the bid size
         - If net position is negative (short), we might want to reduce the ask size
         - If net position is near target, use base_order_size
        This is a naive example.
        """
        position_diff = abs(current_position - self.target_position)
        scale = 1.0 + min(position_diff / self.max_inventory, 1.0)  # max scale = 2.0
        dynamic_size = self.base_order_size * scale
        dynamic_size = max(
            self.base_order_size * 0.5, min(dynamic_size, self.base_order_size * 2.0)
        )
        return dynamic_size

    def values_changed(
        self, current_position: float, spread: float, order_size: float
    ) -> bool:
        """
        Return True if any of (net position, spread, order_size) changed
        beyond the float tolerance from the previous iteration.
        """
        if (
            self.prev_net_position is None
            or self.prev_spread is None
            or self.prev_order_size is None
        ):
            return True

        if (
            abs(current_position - self.prev_net_position) > self.float_tolerance
            or abs(spread - self.prev_spread) > self.float_tolerance
            or abs(order_size - self.prev_order_size) > self.float_tolerance
        ):
            return True

        return False

    async def place_orders(self):
        """
        Main logic to:
         1) Determine if anything changed from last iteration
         2) If changed, cancel existing orders and place new ones
         3) Otherwise do nothing
        """
        current_position = self.get_net_position()
        spread = self.calculate_spread(current_position)
        order_size = self.calculate_order_size(current_position)

        logger.info(f"Current net position: {current_position:.4f}")
        logger.info(f"Calculated dynamic spread: {spread * 100:.4f}%")
        logger.info(f"Calculated order size: {order_size:.4f} base assets")

        # Check if the new values differ from the previous iteration
        if not self.values_changed(current_position, spread, order_size):
            logger.info(
                "No changes in net position/spread/size => skipping order placement."
            )
            return

        logger.info("Changes detected => Placing new orders.")

        # Update stored previous iteration values
        self.prev_net_position = current_position
        self.prev_spread = spread
        self.prev_order_size = order_size

        base_size = int(order_size * BASE_PRECISION)
        spread_offset = int(spread * PRICE_PRECISION)

        bid_params = OrderParams(
            order_type=OrderType.Oracle(),  # type: ignore
            market_type=MarketType.Perp(),  # type: ignore
            direction=PositionDirection.Long(),  # type: ignore
            user_order_id=1,
            base_asset_amount=base_size,
            price=0,  # Use oracle
            market_index=self.market_index,
            reduce_only=False,
            immediate_or_cancel=False,
            trigger_price=0,
            oracle_price_offset=-spread_offset,
        )

        ask_params = OrderParams(
            order_type=OrderType.Oracle(),  # type: ignore
            market_type=MarketType.Perp(),  # type: ignore
            direction=PositionDirection.Short(),  # type: ignore
            user_order_id=2,
            base_asset_amount=base_size,
            price=0,  # Use oracle
            market_index=self.market_index,
            reduce_only=False,
            immediate_or_cancel=False,
            trigger_price=0,
            oracle_price_offset=spread_offset,
        )

        try:
            logger.info("Cancelling and placing orders...")
            await self.drift_client.cancel_and_place_orders(
                cancel_params=(None, None, None),
                place_order_params=[bid_params, ask_params],
                sub_account_id=0,
            )
            logger.info(f"Orders placed with spread {spread*100:.4f}%.")
        except Exception as e:
            logger.error(f"Failed to cancel and place orders: {str(e)}")
            raise


async def main():
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def handle_sigterm():
        logger.warning("Received shutdown signal. Stopping gracefully...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_sigterm)

    drift_client = await get_drift_client()

    maker = OracleMaker(
        drift_client=drift_client,
        market_index=0,  # e.g. 0 => SOL-PERP
        target_position=0.0,  # remain neutral
        max_inventory=5.0,
        base_order_size=1.0,
        base_spread=0.001,  # 0.1%
        float_tolerance=1e-6,  # compare changes with tolerance
    )

    try:
        while not stop_event.is_set():
            await maker.place_orders()
            logger.info("Sleeping 1 second before next iteration...")
            await asyncio.sleep(1)

    finally:
        logger.info("Unsubscribing from Drift client...")
        await drift_client.unsubscribe()
        logger.info("Drift client unsubscribed.")
        logger.info("Exiting.")


if __name__ == "__main__":
    asyncio.run(main())
