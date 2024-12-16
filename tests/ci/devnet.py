import asyncio
import os

import pytest
from anchorpy.provider import Wallet
from pytest import mark
from solana.rpc.async_api import AsyncClient

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.accounts.cache import CachedDriftClientAccountSubscriber
from driftpy.constants.perp_markets import devnet_perp_market_configs
from driftpy.constants.spot_markets import devnet_spot_market_configs
from driftpy.drift_client import DriftClient


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

        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


@pytest.fixture(scope="session")
def rpc_url():
    return os.environ.get("DEVNET_RPC_ENDPOINT")


@mark.asyncio
async def test_devnet_constants(rpc_url: str):
    print()
    print("Checking devnet constants")
    drift_client = DriftClient(
        AsyncClient(rpc_url),
        Wallet.dummy(),
        env="devnet",
        account_subscription=AccountSubscriptionConfig("cached"),
    )

    print("Subscribing to Drift Client")
    await drift_client.subscribe()
    print("Subscribed to Drift Client")

    expected_perp_markets = sorted(
        devnet_perp_market_configs, key=lambda market: market.market_index
    )
    received_perp_markets = sorted(
        drift_client.get_perp_market_accounts(), key=lambda market: market.market_index
    )

    print("==> Received Perp Markets:")
    for market in received_perp_markets:
        print(
            market.market_index,
            market.amm.oracle,
            bytes(market.name).decode("utf-8").strip(),
            market.amm.oracle_source,
        )

    for expected, received in zip(expected_perp_markets, received_perp_markets):
        market_info = f"Market: {received.pubkey} Market Index: {received.market_index}"

        assert (
            expected.market_index == received.market_index
        ), f"Devnet Perp: Expected market index {expected.market_index}, got {received.market_index} {market_info} for {expected.symbol}"

        assert (
            str(expected.oracle) == str(received.amm.oracle)
        ), f"Devnet Perp: Expected oracle {expected.oracle}, got {received.amm.oracle} {market_info} for {expected.symbol}"

        assert (
            str(expected.oracle_source) == str(received.amm.oracle_source)
        ), f"Devnet Perp: Expected oracle source {expected.oracle_source}, got {received.amm.oracle_source} {market_info} for {expected.symbol}"

    expected_spot_markets = sorted(
        devnet_spot_market_configs, key=lambda market: market.market_index
    )
    received_spot_markets = sorted(
        drift_client.get_spot_market_accounts(), key=lambda market: market.market_index
    )

    print("\n==> Received Spot Markets:")
    for market in received_spot_markets:
        print(
            market.market_index,
            market.oracle,
            bytes(market.name).decode("utf-8").strip(),
            market.oracle_source,
        )

    for expected, received in zip(expected_spot_markets, received_spot_markets):
        market_info = f"Market: {received.pubkey} Market Index: {received.market_index}"

        assert (
            expected.market_index == received.market_index
        ), f"Devnet Spot: Expected market index {expected.market_index}, got {received.market_index} {market_info} for {expected.symbol}"

        assert (
            str(expected.oracle) == str(received.oracle)
        ), f"Devnet Spot: Expected oracle {expected.oracle}, got {received.oracle} {market_info} for {expected.symbol}"

        assert (
            str(expected.oracle_source) == str(received.oracle_source)
        ), f"Devnet Spot: Expected oracle source {expected.oracle_source}, got {received.oracle_source} {market_info} for {expected.symbol}"


@mark.asyncio
async def test_devnet_cached(rpc_url: str):
    print()
    drift_client = DriftClient(
        AsyncClient(rpc_url),
        Wallet.dummy(),
        env="devnet",
        account_subscription=AccountSubscriptionConfig("cached"),
    )

    print("Subscribing to Drift Client")

    await drift_client.subscribe()

    print("Subscribed to Drift Client")

    perp_markets = drift_client.get_perp_market_accounts()
    print(f"1. Got: {len(perp_markets)}")
    assert (
        len(perp_markets) == len(devnet_perp_market_configs)
    ), f"Expected {len(devnet_perp_market_configs)} perp markets, got {len(perp_markets)}"

    spot_markets = drift_client.get_spot_market_accounts()
    print(f"1. Got: {len(spot_markets)}")
    assert (
        len(spot_markets) == len(devnet_spot_market_configs)
    ), f"Expected {len(devnet_spot_market_configs)} spot markets, got {len(spot_markets)}"

    assert drift_client.account_subscriber is not None
    assert isinstance(
        drift_client.account_subscriber, CachedDriftClientAccountSubscriber
    )
    await drift_client.account_subscriber.update_cache()

    perp_markets = drift_client.get_perp_market_accounts()
    print(f"2. Got: {len(perp_markets)}")
    assert (
        len(perp_markets) == len(devnet_perp_market_configs)
    ), f"Expected {len(devnet_perp_market_configs)} perp markets, got {len(perp_markets)}"

    spot_markets = drift_client.get_spot_market_accounts()
    print(f"2. Got: {len(spot_markets)}")
    assert (
        len(spot_markets) == len(devnet_spot_market_configs)
    ), f"Expected {len(devnet_spot_market_configs)} spot markets, got {len(spot_markets)}"

    print("Unsubscribing from Drift Client")

    await drift_client.unsubscribe()

    print("Unsubscribed from Drift Client")


@mark.asyncio
async def test_devnet_ws(rpc_url: str):
    print()
    drift_client = DriftClient(
        AsyncClient(rpc_url),
        Wallet.dummy(),
        env="devnet",
        account_subscription=AccountSubscriptionConfig("websocket"),
    )

    print("Subscribing to Drift Client")
    await drift_client.subscribe()
    print("Subscribed to Drift Client")

    perp_markets = drift_client.get_perp_market_accounts()
    print(f"1. Got: {len(perp_markets)}")
    assert (
        len(perp_markets) == len(devnet_perp_market_configs)
    ), f"Expected {len(devnet_perp_market_configs)} perp markets, got {len(perp_markets)}"

    spot_markets = drift_client.get_spot_market_accounts()
    print(f"1. Got: {len(spot_markets)}")
    assert (
        len(spot_markets) == len(devnet_spot_market_configs)
    ), f"Expected {len(devnet_spot_market_configs)} spot markets, got {len(spot_markets)}"

    # wait for some updates
    await asyncio.sleep(10)

    perp_markets = drift_client.get_perp_market_accounts()
    print(f"2. Got: {len(perp_markets)}")
    assert (
        len(perp_markets) == len(devnet_perp_market_configs)
    ), f"Expected {len(devnet_perp_market_configs)} perp markets, got {len(perp_markets)}"

    spot_markets = drift_client.get_spot_market_accounts()
    print(f"2. Got: {len(spot_markets)}")
    assert (
        len(spot_markets) == len(devnet_spot_market_configs)
    ), f"Expected {len(devnet_spot_market_configs)} spot markets, got {len(spot_markets)}"

    print("Unsubscribing from Drift Client")

    await drift_client.unsubscribe()

    print("Unsubscribed from Drift Client")
