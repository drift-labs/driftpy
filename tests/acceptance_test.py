import os
import json

from pytest import mark
from pytest_asyncio import fixture as async_fixture
from anchorpy import workspace_fixture, Wallet, Provider

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.constants.numeric_constants import (
    QUOTE_PRECISION,
    BASE_PRECISION,
)
from math import sqrt

from driftpy.constants.config import configs
from driftpy.constants.numeric_constants import PRICE_PRECISION, AMM_RESERVE_PRECISION
from driftpy.drift_client import DriftClient

from driftpy.addresses import *
from driftpy.types import *
from driftpy.accounts import *
from solders.keypair import Keypair

# from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient


MANTISSA_SQRT_SCALE = int(sqrt(PRICE_PRECISION))
AMM_INITIAL_QUOTE_ASSET_AMOUNT = int((5 * AMM_RESERVE_PRECISION) * MANTISSA_SQRT_SCALE)
AMM_INITIAL_BASE_ASSET_AMOUNT = int((5 * AMM_RESERVE_PRECISION) * MANTISSA_SQRT_SCALE)
PERIODICITY = 60 * 60  # 1 HOUR
USDC_AMOUNT = int(10 * QUOTE_PRECISION)
MARKET_INDEX = 0

workspace = workspace_fixture(
    "protocol-v2", build_cmd="anchor build --skip-lint", scope="session"
)


@async_fixture(scope="session")
async def drift_client() -> DriftClient:
    with open(os.path.expanduser(os.environ["ANCHOR_WALLET"]), "r") as f:
        secret = json.load(f)
    kp = Keypair.from_bytes(bytes(secret))

    wallet = Wallet(kp)
    connection = AsyncClient("https://api.devnet.solana.com")

    drift_client = DriftClient(
        connection,
        wallet,
        "devnet",
        account_subscription=AccountSubscriptionConfig("cached"),
    )
    await drift_client.subscribe()
    return drift_client


@mark.asyncio
async def test_get_perp_market(
    drift_client: DriftClient,
):
    ix = drift_client.get_place_perp_order_ix(
        OrderParams(
            order_type=OrderType.LIMIT(),
            market_type=MarketType.PERP(),
            direction=PositionDirection.LONG(),
            user_order_id=0,
            base_asset_amount=BASE_PRECISION,
            price=10 * PRICE_PRECISION,
            market_index=0,
            reduce_only=False,
            post_only=PostOnlyParams.NONE(),
            immediate_or_cancel=False,
            max_ts=None,
            trigger_price=None,
            trigger_condition=OrderTriggerCondition.ABOVE(),
            oracle_price_offset=None,
            auction_duration=None,
            auction_start_price=None,
            auction_end_price=None,
        )
    )

    assert len(ix.accounts) > 5

    assert (
        str(ix.accounts[3].pubkey) == "5SSkXsEKQepHHAewytPVwdej4epN1nxgLVM84L4KXgy7"
    ), "incorrect spot oracle address"
    assert (
        str(ix.accounts[4].pubkey) == "J83w4HKfqxwcq3BEMMkPFSppX3gqekLyLJBexebFVkix"
    ), "incorrect perp oracle address"
