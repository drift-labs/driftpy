import asyncio
import logging
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Union, cast

from aiohttp import web
from anchorpy.provider import Wallet
from dotenv import load_dotenv
from jit_proxy.jit_proxy_client import JitProxyClient, PriceType
from jit_proxy.jitter.base_jitter import AuctionSubscriber, JitParams
from jit_proxy.jitter.jitter_shotgun import JitterShotgun
from jit_proxy.jitter.jitter_sniper import JitterSniper
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Processed
from solana.rpc.types import TxOpts
from solders.pubkey import Pubkey

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.auction_subscriber.grpc_auction_subscriber import GrpcAuctionSubscriber
from driftpy.auction_subscriber.types import (
    GrpcAuctionSubscriberConfig,
)
from driftpy.constants.config import DriftEnv
from driftpy.constants.numeric_constants import (
    BASE_PRECISION,
    PERCENTAGE_PRECISION,
    PRICE_PRECISION,
    QUOTE_PRECISION,
)
from driftpy.dlob.client_types import DLOBClientConfig
from driftpy.dlob.dlob import DLOB
from driftpy.dlob.dlob_node import DLOBNode
from driftpy.dlob.dlob_subscriber import DLOBSubscriber
from driftpy.drift_client import DriftClient
from driftpy.keypair import load_keypair
from driftpy.math.amm import calculate_bid_ask_price
from driftpy.math.conversion import convert_to_number
from driftpy.slot.slot_subscriber import SlotSubscriber
from driftpy.tx.fast_tx_sender import FastTxSender
from driftpy.types import (
    GrpcConfig,
    MarketType,
    OraclePriceData,
    PerpMarketAccount,
    SpotMarketAccount,
    TxParams,
    is_variant,
)
from driftpy.user_map.user_map import UserMap
from driftpy.user_map.user_map_config import UserMapConfig, WebsocketConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def decode_name(bytes_list: list[int]) -> str:
    byte_array = bytes(bytes_list)
    return byte_array.decode("utf-8").strip()


def get_best_limit_bid_exclusionary(
    dlob: DLOB,
    market_index: int,
    market_type: MarketType,
    slot: int,
    oracle_price_data: OraclePriceData,
    excluded_pubkey: str,
    excluded_user_accounts_and_order: list[tuple[str, int]] = [],
    uncross: bool = False,
) -> Optional[DLOBNode]:
    bids = dlob.get_resting_limit_bids(
        market_index, slot, market_type, oracle_price_data
    )

    for bid in bids:
        if hasattr(bid, "user_account"):
            if str(bid.user_account) == excluded_pubkey:
                continue
            if hasattr(bid, "order"):
                order_id = bid.order.order_id
                price = bid.order.price
                if uncross and price > oracle_price_data.price:
                    continue
                if any(
                    entry[0] == str(bid.user_account) and entry[1] == (order_id or -1)
                    for entry in excluded_user_accounts_and_order
                ):
                    continue

        return bid

    return None


def get_best_limit_ask_exclusionary(
    dlob: DLOB,
    market_index: int,
    market_type: MarketType,
    slot: int,
    oracle_price_data: OraclePriceData,
    excluded_pubkey: str,
    excluded_user_accounts_and_order: list[tuple[str, int]] = [],
    uncross: bool = False,
) -> Optional[DLOBNode]:
    asks = dlob.get_resting_limit_asks(
        market_index, slot, market_type, oracle_price_data
    )

    for ask in asks:
        if hasattr(ask, "user_account"):
            if str(ask.user_account) == excluded_pubkey:
                continue
            if hasattr(ask, "order"):
                order_id = ask.order.order_id
                price = ask.order.price
                if uncross and price < oracle_price_data.price:
                    continue
                if any(
                    entry[0] == str(ask.user_account) and entry[1] == (order_id or -1)
                    for entry in excluded_user_accounts_and_order
                ):
                    continue

        return ask

    return None


def calculate_base_amount_to_mm_perp(
    perp_market_account: PerpMarketAccount,
    net_spot_market_value: int,
    target_leverage: float = 1,
):
    base_price_normalized = convert_to_number(
        perp_market_account.amm.historical_oracle_data.last_oracle_price_twap
    )
    tc_normalized = convert_to_number(net_spot_market_value, QUOTE_PRECISION)
    target_leverage *= 0.95
    max_base = (tc_normalized / base_price_normalized) * target_leverage
    logger.info(f"{net_spot_market_value} -> {tc_normalized}")
    logger.info(
        f"(mkt index: {decode_name(perp_market_account.name)}) base to market make (targetLvg={target_leverage}): {max_base} = {tc_normalized} / {base_price_normalized} * {target_leverage}"
    )
    return max_base


def calculate_base_amount_to_mm_spot(
    spot_market_account: SpotMarketAccount,
    net_spot_market_value: int,
    target_leverage: float = 1,
):
    base_price_normalized = convert_to_number(
        spot_market_account.historical_oracle_data.last_oracle_price_twap
    )
    tc_normalized = convert_to_number(net_spot_market_value, QUOTE_PRECISION)
    logger.info(f" {net_spot_market_value} -> {tc_normalized}")
    target_leverage *= 0.95
    market_symbol = decode_name(spot_market_account.name)

    max_base = (tc_normalized / base_price_normalized) * target_leverage
    logger.info(
        f"(mkt index: {market_symbol}) base to market make (targetLvg={target_leverage}): "
        f"{max_base} = {tc_normalized} / {base_price_normalized} * {target_leverage}"
    )
    return max_base


def is_perp_market_volatile(
    perp_market_account: PerpMarketAccount,
    oracle_price_data: OraclePriceData,
    volatile_threshold: float = 0.005,
):
    twap_price = (
        perp_market_account.amm.historical_oracle_data.last_oracle_price_twap5min
    )
    last_price = perp_market_account.amm.historical_oracle_data.last_oracle_price
    current_price = oracle_price_data.price

    min_denom = min(current_price, last_price, twap_price)
    c_vs_l = abs((current_price - last_price) * PRICE_PRECISION // min_denom)
    c_vs_t = abs((current_price - twap_price) * PRICE_PRECISION // min_denom)

    recent_std = perp_market_account.amm.oracle_std * PRICE_PRECISION // min_denom
    c_vs_l_percentage = c_vs_l / PERCENTAGE_PRECISION
    c_vs_t_percentage = c_vs_t / PERCENTAGE_PRECISION
    recent_std_percentage = recent_std / PERCENTAGE_PRECISION
    return (
        recent_std_percentage > volatile_threshold
        or c_vs_t_percentage > volatile_threshold
        or c_vs_l_percentage > volatile_threshold
    )


def is_spot_market_volatile(
    spot_market_account: SpotMarketAccount,
    oracle_price_data: OraclePriceData,
    volatile_threshold: float = 0.005,
):
    twap_price = spot_market_account.historical_oracle_data.last_oracle_price_twap5min
    last_price = spot_market_account.historical_oracle_data.last_oracle_price
    current_price = oracle_price_data.price
    min_denom = min(current_price, last_price, twap_price)
    c_vs_l = abs((current_price - last_price) * PRICE_PRECISION // min_denom)
    c_vs_t = abs((current_price - twap_price) * PRICE_PRECISION // min_denom)
    c_vs_l_percentage = c_vs_l / PERCENTAGE_PRECISION
    c_vs_t_percentage = c_vs_t / PERCENTAGE_PRECISION
    return (
        c_vs_t_percentage > volatile_threshold or c_vs_l_percentage > volatile_threshold
    )


@dataclass
class JitMakerConfig:
    bot_id: str
    market_indexes: list[int]
    sub_accounts: list[int]
    market_type: MarketType
    target_leverage: float = 1.0
    spread: float = 0.0


class JitMaker:
    def __init__(
        self,
        config: JitMakerConfig,
        drift_client: DriftClient,
        usermap: UserMap,
        jitter: Union[JitterSniper, JitterShotgun],
        drift_env: DriftEnv,
    ):
        self.drift_env = drift_env
        self.lookup_tables = None
        self.tasks: list[asyncio.Task] = []
        self.default_interval_ms = 30_000

        self.task_lock = asyncio.Lock()
        self.watchdog = asyncio.Lock()
        self.watchdog_last_pat = time.time()

        self.name = config.bot_id
        self.sub_accounts: list[int] = config.sub_accounts  # type: ignore
        self.market_indexes: list[int] = config.market_indexes  # type: ignore
        self.market_type = config.market_type
        self.target_leverage = config.target_leverage
        self.spread = config.spread

        self.drift_client = drift_client
        self.usermap = usermap
        self.jitter = jitter
        self.slot_subscriber = SlotSubscriber(self.drift_client)

        dlob_config = DLOBClientConfig(
            self.drift_client, self.usermap, self.slot_subscriber, 30
        )
        self.dlob_subscriber = DLOBSubscriber(config=dlob_config)

    async def init(self):
        logger.info(f"Initializing {self.name}")

        init_len = len(self.sub_accounts)
        dedup_len = len(list(set(self.sub_accounts)))
        if init_len != dedup_len:
            raise ValueError(
                "You CANNOT make multiple markets with the same sub account id"
            )

        market_len = len(self.market_indexes)
        if dedup_len != market_len:
            raise ValueError("You must have 1 sub account id per market to jit")

        await self.drift_client.subscribe()
        await self.slot_subscriber.subscribe()
        await self.dlob_subscriber.subscribe()
        await self.jitter.subscribe()

        self.lookup_tables = [await self.drift_client.fetch_market_lookup_table()]
        logger.info(f"Initialized {self.name}")

    async def reset(self):
        for task in self.tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self.tasks.clear()
        logger.info(f"{self.name} reset complete")

    def get_tasks(self):
        return self.tasks

    async def start_interval_loop(self, interval_ms: int = 1000):
        async def interval_loop():
            try:
                while True:
                    await self.run_periodic_tasks()
                    await asyncio.sleep(interval_ms / 1000)
            except asyncio.CancelledError:
                pass

        task = asyncio.create_task(interval_loop())
        self.tasks.append(task)
        logger.info(f"{self.name} Bot started! driftEnv: {self.drift_env}")

    async def health_check(self):
        healthy = False
        async with self.watchdog:
            healthy = self.watchdog_last_pat > time.time() - (
                2 * self.default_interval_ms // 1_000
            )
        return healthy

    async def run_periodic_tasks(self):
        start = time.time()
        ran = False
        try:
            async with self.task_lock:
                logger.info(
                    f"{datetime.fromtimestamp(start).isoformat()} running jit periodic tasks"
                )

                for i in range(len(self.market_indexes)):
                    if is_variant(self.market_type, "Perp"):
                        await self.jit_perp(i)
                    else:
                        await self.jit_spot(i)

                await asyncio.sleep(10)

                logger.info(f"done: {time.time() - start}s")
                ran = True
        except Exception as e:
            raise e
        finally:
            if ran:
                duration = time.time() - start
                logger.info(f"{self.name} took {duration} s to run")

                async with self.watchdog:
                    self.watchdog_last_pat = time.time()

    async def jit_perp(self, index: int):
        perp_idx = self.market_indexes[index]
        sub_id = self.sub_accounts[index]
        self.drift_client.switch_active_user(sub_id)

        drift_user = self.drift_client.get_user(sub_id)
        perp_market_account = self.drift_client.get_perp_market_account(perp_idx)
        oracle_price_data = self.drift_client.get_oracle_price_data_for_perp_market(
            perp_idx
        )

        num_markets_for_subaccount = len(
            [num for num in self.sub_accounts if num == sub_id]
        )

        target_leverage = self.target_leverage / num_markets_for_subaccount
        actual_leverage = drift_user.get_leverage() / 10_000

        max_base = calculate_base_amount_to_mm_perp(
            perp_market_account,  # type: ignore
            drift_user.get_net_spot_market_value(None),
            target_leverage,
        )

        overlevered_long = False
        overlevered_short = False

        if actual_leverage >= target_leverage:
            logger.warning(
                f"jit maker at or above max leverage actual: {actual_leverage} target: {target_leverage}"
            )
            overlevered_base_asset_amount = drift_user.get_perp_position(
                perp_idx
            ).base_asset_amount  # type: ignore
            if overlevered_base_asset_amount > 0:
                overlevered_long = True
            elif overlevered_base_asset_amount < 0:
                overlevered_short = True

        def user_filter(user_account, user_key: str, order) -> bool:
            skip = user_key == str(drift_user.user_public_key)

            if is_perp_market_volatile(
                perp_market_account,
                oracle_price_data,
                0.015,  # type: ignore
            ):
                logger.info(
                    f"Skipping, Market: {perp_market_account.market_index} is volatile"  # type: ignore
                )
                skip = True

            if skip:
                logger.info(f"Skipping user: {user_key}")

            return skip

        self.jitter.set_user_filter(user_filter)

        best_bid = get_best_limit_bid_exclusionary(
            self.dlob_subscriber.dlob,  # type: ignore
            perp_market_account.market_index,  # type: ignore
            MarketType.Perp(),
            oracle_price_data.slot,  # type: ignore
            oracle_price_data,  # type: ignore
            str(drift_user.user_public_key),
            uncross=False,
        )

        best_ask = get_best_limit_ask_exclusionary(
            self.dlob_subscriber.dlob,  # type: ignore
            perp_market_account.market_index,  # type: ignore
            MarketType.Perp(),
            oracle_price_data.slot,  # type: ignore
            oracle_price_data,  # type: ignore
            str(drift_user.user_public_key),
            uncross=False,
        )

        (amm_bid, amm_ask) = calculate_bid_ask_price(
            perp_market_account.amm, oracle_price_data, True
        )

        if best_bid is not None:
            best_dlob_price = best_bid.get_price(
                oracle_price_data,
                self.dlob_subscriber.slot_source.get_slot(),  # type: ignore
            )

            if best_dlob_price > amm_ask:
                best_bid_price = amm_ask
            else:
                best_bid_price = max(amm_bid, best_dlob_price)

        else:
            best_bid_price = amm_bid

        if best_ask is not None:
            best_dlob_price = best_ask.get_price(
                oracle_price_data,
                self.dlob_subscriber.slot_source.get_slot(),  # type: ignore
            )

            if best_dlob_price < amm_bid:
                best_ask_price = amm_bid
            else:
                best_ask_price = min(amm_ask, best_dlob_price)
        else:
            best_ask_price = amm_ask

        logger.info(f"best bid price: {best_bid_price}")
        logger.info(f"best ask price: {best_ask_price}")

        logger.info(f"oracle price: {oracle_price_data.price}")  # type: ignore

        bid_offset = math.floor(
            best_bid_price - ((1 + self.spread) * oracle_price_data.price)  # type: ignore
        )
        ask_offset = math.floor(
            best_ask_price - ((1 - self.spread) * oracle_price_data.price)  # type: ignore
        )

        logger.info(f"max_base: {max_base}")

        perp_min_position = math.floor((-max_base) * BASE_PRECISION)
        perp_max_position = math.floor((max_base) * BASE_PRECISION)
        if overlevered_long:
            perp_max_position = 0
        elif overlevered_short:
            perp_min_position = 0

        new_perp_params = JitParams(
            bid=bid_offset,
            ask=ask_offset,
            min_position=perp_min_position,
            max_position=perp_max_position,
            price_type=PriceType.Oracle(),
            sub_account_id=sub_id,
        )

        self.jitter.update_perp_params(perp_idx, new_perp_params)
        logger.info(
            f"jitter perp params updated, market_index: {perp_idx}, bid: {new_perp_params.bid}, ask: {new_perp_params.ask} "
            f"min_position: {new_perp_params.min_position}, max_position: {new_perp_params.max_position}"
        )

    async def jit_spot(self, index: int):
        spot_idx = self.market_indexes[index]
        sub_id = self.sub_accounts[index]
        self.drift_client.switch_active_user(sub_id)

        drift_user = self.drift_client.get_user(sub_id)
        spot_market_account = self.drift_client.get_spot_market_account(spot_idx)
        oracle_price_data = self.drift_client.get_oracle_price_data_for_spot_market(
            spot_idx
        )

        num_markets_for_subaccount = len(
            [num for num in self.sub_accounts if num == sub_id]
        )

        target_leverage = self.target_leverage / num_markets_for_subaccount
        actual_leverage = drift_user.get_leverage() / 10_000

        max_base = calculate_base_amount_to_mm_spot(
            spot_market_account,  # type: ignore
            drift_user.get_net_spot_market_value(None),
            target_leverage,
        )

        overlevered_long = False
        overlevered_short = False

        if actual_leverage >= target_leverage:
            logger.warning(
                f"jit maker at or above max leverage actual: {actual_leverage} target: {target_leverage}"
            )
            overlevered_base_asset_amount = drift_user.get_spot_position(
                spot_idx
            ).scaled_balance  # type: ignore
            if overlevered_base_asset_amount > 0:
                overlevered_long = True
            elif overlevered_base_asset_amount < 0:
                overlevered_short = True

        def user_filter(user_account, user_key: str, order) -> bool:
            skip = user_key == str(drift_user.user_public_key)

            if is_spot_market_volatile(
                spot_market_account,
                oracle_price_data,
                0.015,  # type: ignore
            ):
                logger.info(
                    f"Skipping, Market: {spot_market_account.market_index} is volatile"  # type: ignore
                )
                skip = True

            if skip:
                logger.info(f"Skipping user: {user_key}")

            return skip

        self.jitter.set_user_filter(user_filter)

        best_bid = get_best_limit_bid_exclusionary(
            self.dlob_subscriber.dlob,  # type: ignore
            spot_market_account.market_index,  # type: ignore
            MarketType.Spot(),
            oracle_price_data.slot,  # type: ignore
            oracle_price_data,  # type: ignore
            str(drift_user.user_public_key),
            uncross=True,
        )

        best_ask = get_best_limit_ask_exclusionary(
            self.dlob_subscriber.dlob,  # type: ignore
            spot_market_account.market_index,  # type: ignore
            MarketType.Spot(),
            oracle_price_data.slot,  # type: ignore
            oracle_price_data,  # type: ignore
            str(drift_user.user_public_key),
            uncross=True,
        )

        if not best_bid or not best_ask:
            logger.warning("skipping, no best bid / ask")
            return

        best_bid_price = best_bid.get_price(
            oracle_price_data,
            self.dlob_subscriber.slot_source.get_slot(),  # type: ignore
        )

        best_ask_price = best_ask.get_price(
            oracle_price_data,
            self.dlob_subscriber.slot_source.get_slot(),  # type: ignore
        )

        logger.info(f"best bid price: {best_bid_price}")
        logger.info(f"best ask price: {best_ask_price}")

        logger.info(f"oracle price: {oracle_price_data.price}")  # type: ignore

        bid_offset = math.floor(
            best_bid_price - ((1 + self.spread) * oracle_price_data.price)  # type: ignore
        )
        ask_offset = math.floor(
            best_ask_price - ((1 - self.spread) * oracle_price_data.price)  # type: ignore
        )

        logger.info(f"max_base: {max_base}")

        spot_market_precision = 10**spot_market_account.decimals  # type: ignore

        spot_min_position = math.floor((-max_base) * spot_market_precision)
        spot_max_position = math.floor((max_base) * spot_market_precision)
        if overlevered_long:
            spot_max_position = 0
        elif overlevered_short:
            spot_min_position = 0

        new_spot_params = JitParams(
            bid=min(bid_offset, -1),
            ask=max(ask_offset, 1),
            min_position=spot_min_position,
            max_position=spot_max_position,
            price_type=PriceType.Oracle(),
            sub_account_id=sub_id,
        )

        self.jitter.update_spot_params(spot_idx, new_spot_params)
        logger.info(
            f"jitter spot params updated, market_index: {spot_idx}, bid: {new_spot_params.bid}, ask: {new_spot_params.ask} "
            f"min_position: {new_spot_params.min_position}, max_position: {new_spot_params.max_position}"
        )


def make_health_check_handler(jit_maker):
    async def health_check_handler(request):
        healthy = await jit_maker.health_check()
        if healthy:
            return web.Response(status=200)  # OK status for healthy
        else:
            return web.Response(status=503)  # Service Unavailable for unhealthy

    return health_check_handler


async def start_server(jit_maker):
    app = web.Application()
    health_handler = make_health_check_handler(jit_maker)
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()


async def main():
    load_dotenv()
    secret = os.getenv("PRIVATE_KEY")
    url = os.getenv("RPC_TRITON")
    rpc_url = url
    rpc_fqdn = os.environ.get("RPC_FQDN")  # e.g. "my-geyser-endpoint.com:443"
    x_token = os.environ.get("X_TOKEN")  # grpc auth token

    if not (rpc_fqdn and x_token and secret and rpc_url):
        raise ValueError("RPC_FQDN, X_TOKEN, PRIVATE_KEY, and RPC_TRITON must be set")

    kp = load_keypair(secret)
    wallet = Wallet(kp)

    connection = AsyncClient(url)
    commitment = Processed
    tx_opts = TxOpts(skip_confirmation=False, preflight_commitment=commitment)
    fast_tx_sender = FastTxSender(connection, tx_opts, 3)

    drift_client = DriftClient(
        connection,
        wallet,
        "mainnet",
        account_subscription=AccountSubscriptionConfig(
            "grpc",
            grpc_config=GrpcConfig(
                endpoint=rpc_fqdn,
                token=x_token,
            ),
        ),
        tx_params=TxParams(700_000, 50_000),  # crank priority fees way up
        opts=tx_opts,
        tx_sender=fast_tx_sender,
    )
    await drift_client.subscribe()
    # await asyncio.sleep(10)

    auction_subscriber_config = GrpcAuctionSubscriberConfig(
        drift_client=drift_client,
        grpc_config=GrpcConfig(endpoint=rpc_fqdn, token=x_token),
        commitment=commitment,
    )
    grpc_auction_subscriber = GrpcAuctionSubscriber(auction_subscriber_config)
    usermap_config = UserMapConfig(drift_client, WebsocketConfig())
    usermap = UserMap(usermap_config)

    await usermap.subscribe()

    jit_proxy_client = JitProxyClient(
        drift_client,
        Pubkey.from_string("J1TnP8zvVxbtF5KFp5xRmWuvG9McnhzmBd9XGfCyuxFP"),
    )

    jitter = JitterShotgun(
        drift_client,
        cast(AuctionSubscriber, grpc_auction_subscriber),
        jit_proxy_client,
        True,
    )

    jit_maker_perp_config = JitMakerConfig(
        bot_id="jit maker",
        market_indexes=[0],
        sub_accounts=[0],
        market_type=MarketType.Perp(),  # type: ignore
        spread=-0.01,
    )

    for sub_id in jit_maker_perp_config.sub_accounts:
        await drift_client.add_user(sub_id)

    jit_maker = JitMaker(
        jit_maker_perp_config, drift_client, usermap, jitter, "mainnet"
    )

    # This is an example of a spot JIT maker that will JIT the SOL market
    # jit_maker_spot_config = JitMakerConfig(
    #     "jit maker", [1], [0], MarketType.Spot()
    # )

    # for sub_id in jit_maker_spot_config.sub_accounts:
    #     await drift_client.add_user(sub_id)

    # jit_maker = JitMaker(
    #     jit_maker_spot_config, drift_client, usermap, jitter, "mainnet"
    # )

    asyncio.create_task(start_server(jit_maker))

    await jit_maker.init()
    await jit_maker.start_interval_loop(10_000)
    await asyncio.gather(*jit_maker.get_tasks())
    print(f"Healthy?: {await jit_maker.health_check()}")
    await jit_maker.reset()


if __name__ == "__main__":
    asyncio.run(main())
