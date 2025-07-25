import asyncio
import os

import dotenv
import pytest
from anchorpy import Wallet
from pytest import mark
from solana.rpc.async_api import AsyncClient

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.constants.perp_markets import mainnet_perp_market_configs
from driftpy.constants.spot_markets import mainnet_spot_market_configs
from driftpy.drift_client import DriftClient

dotenv.load_dotenv()


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the session."""
    try:
        loop = asyncio.get_event_loop_policy().new_event_loop()
        asyncio.set_event_loop(loop)
        yield loop
    finally:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()

        # Allow tasks to respond to cancellation
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


@pytest.fixture(scope="session")
def rpc_url():
    return os.environ.get("MAINNET_RPC_ENDPOINT")


@mark.asyncio
async def test_mainnet_constants(rpc_url: str):
    print("Checking mainnet constants")
    drift_client = DriftClient(
        AsyncClient(rpc_url),
        Wallet.dummy(),
        env="mainnet",
        account_subscription=AccountSubscriptionConfig("cached"),
    )

    print("Subscribing to Drift Client")
    await drift_client.subscribe()
    print("Subscribed to Drift Client")

    expected_perp_markets = sorted(
        mainnet_perp_market_configs, key=lambda market: market.market_index
    )
    received_perp_markets = sorted(
        drift_client.get_perp_market_accounts(), key=lambda market: market.market_index
    )

    for expected, received in zip(expected_perp_markets, received_perp_markets):
        assert (
            expected.market_index == received.market_index
        ), f"Perp: Expected market index {expected.market_index}, got {received.market_index} Market: {received.pubkey}"
        assert (
            str(expected.oracle) == str(received.amm.oracle)
        ), f"Perp: Expected oracle {expected.oracle}, got {received.amm.oracle} Market: {received.pubkey} Market Index: {received.market_index}"
        assert (
            str(expected.oracle_source) == str(received.amm.oracle_source)
        ), f"Perp: Expected oracle source {expected.oracle_source}, got {received.amm.oracle_source} Market: {received.pubkey} Market Index: {received.market_index}"

    expected_spot_markets = sorted(
        mainnet_spot_market_configs, key=lambda market: market.market_index
    )
    received_spot_markets = sorted(
        drift_client.get_spot_market_accounts(), key=lambda market: market.market_index
    )

    for expected, received in zip(expected_spot_markets, received_spot_markets):
        assert (
            expected.market_index == received.market_index
        ), f"Spot: Expected market index {expected.market_index}, got {received.market_index} Market: {received.pubkey}"
        assert (
            str(expected.oracle) == str(received.oracle)
        ), f"Spot: Expected oracle {expected.oracle}, got {received.oracle} Market: {received.pubkey} Market Index: {received.market_index}"
        assert (
            str(expected.oracle_source) == str(received.oracle_source)
        ), f"Spot: Expected oracle source {expected.oracle_source}, got {received.oracle_source} Market: {received.pubkey} Market Index: {received.market_index}"


@mark.asyncio
async def test_mainnet_cached(rpc_url: str):
    print("Checking mainnet cached subscription")
    drift_client = DriftClient(
        AsyncClient(rpc_url),
        Wallet.dummy(),
        env="mainnet",
        account_subscription=AccountSubscriptionConfig("cached"),
    )

    print("Subscribing to Drift Client")
    await drift_client.subscribe()
    print("Subscribed to Drift Client")

    perp_markets = drift_client.get_perp_market_accounts()
    print(f"1. Got: {len(perp_markets)}")
    assert (
        len(perp_markets) == len(mainnet_perp_market_configs)
    ), f"Expected {len(mainnet_perp_market_configs)} perp markets, got {len(perp_markets)}"

    spot_markets = drift_client.get_spot_market_accounts()
    print(f"1. Got: {len(spot_markets)}")
    assert (
        len(spot_markets) == len(mainnet_spot_market_configs)
    ), f"Expected {len(mainnet_spot_market_configs)} spot markets, got {len(spot_markets)}"

    await drift_client.account_subscriber.update_cache()

    perp_markets = drift_client.get_perp_market_accounts()
    print(f"2. Got: {len(perp_markets)}")
    assert (
        len(perp_markets) == len(mainnet_perp_market_configs)
    ), f"Expected {len(mainnet_perp_market_configs)} perp markets, got {len(perp_markets)}"

    spot_markets = drift_client.get_spot_market_accounts()
    print(f"2. Got: {len(spot_markets)}")
    assert (
        len(spot_markets) == len(mainnet_spot_market_configs)
    ), f"Expected {len(mainnet_spot_market_configs)} spot markets, got {len(spot_markets)}"

    print("Unsubscribing from Drift Client")
    await drift_client.unsubscribe()
    print("Unsubscribed from Drift Client")


@mark.asyncio
async def test_mainnet_ws(rpc_url: str):
    print("Checking mainnet websocket subscription")
    connection = AsyncClient(rpc_url)
    drift_client = DriftClient(
        connection,
        Wallet.dummy(),
        env="mainnet",
        account_subscription=AccountSubscriptionConfig("websocket"),
    )

    print("Subscribing to Drift Client")
    await drift_client.subscribe()
    print("Subscribed to Drift Client")

    perp_markets = drift_client.get_perp_market_accounts()
    print(f"1. Got: {len(perp_markets)}")
    assert (
        len(perp_markets) == len(mainnet_perp_market_configs)
    ), f"Expected {len(mainnet_perp_market_configs)} perp markets, got {len(perp_markets)}"

    spot_markets = drift_client.get_spot_market_accounts()
    print(f"1. Got: {len(spot_markets)}")
    assert (
        len(spot_markets) == len(mainnet_spot_market_configs)
    ), f"Expected {len(mainnet_spot_market_configs)} spot markets, got {len(spot_markets)}"

    # wait for some updates
    await asyncio.sleep(10)

    perp_markets = drift_client.get_perp_market_accounts()
    print(f"2. Got: {len(perp_markets)}")
    assert (
        len(perp_markets) == len(mainnet_perp_market_configs)
    ), f"Expected {len(mainnet_perp_market_configs)} perp markets, got {len(perp_markets)}"

    spot_markets = drift_client.get_spot_market_accounts()
    print(f"2. Got: {len(spot_markets)}")
    assert (
        len(spot_markets) == len(mainnet_spot_market_configs)
    ), f"Expected {len(mainnet_spot_market_configs)} spot markets, got {len(spot_markets)}"

    print("Unsubscribing from Drift Client")
    await drift_client.unsubscribe()
    await connection.close()
    print("Unsubscribed from Drift Client")
