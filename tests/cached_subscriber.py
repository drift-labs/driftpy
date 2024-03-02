import asyncio

from pytest import mark

from anchorpy import Wallet

from solana.rpc.async_api import AsyncClient

from driftpy.constants.config import get_markets_and_oracles
from driftpy.drift_client import DriftClient
from driftpy.account_subscription_config import AccountSubscriptionConfig


@mark.asyncio
async def test_cached():
    print()
    connection = AsyncClient("https://api.mainnet-beta.solana.com")

    perp_market_indexes = [0, 1]
    (
        spot_market_oracles,
        perp_market_oracles,
        spot_market_indexes,
    ) = get_markets_and_oracles("mainnet", perp_market_indexes, None)

    drift_client = DriftClient(
        connection,
        Wallet.dummy(),
        "mainnet",
        perp_market_indexes=perp_market_indexes,
        spot_market_indexes=spot_market_indexes,
        oracle_infos=spot_market_oracles + perp_market_oracles,
        account_subscription=AccountSubscriptionConfig("cached"),
    )

    await drift_client.subscribe()

    # cached perp market
    perp_market_0 = drift_client.get_perp_market_account(0)
    assert perp_market_0
    print("1: found perp market 0")

    # cached perp market
    perp_market_1 = drift_client.get_perp_market_account(1)
    assert perp_market_1
    print("2: found perp market 1")

    # uncached perp market, we'll add this silently
    perp_market_2 = drift_client.get_perp_market_account(2)
    assert not perp_market_2
    print("3: did not find perp market 2")

    # cached spot market
    spot_market_0 = drift_client.get_spot_market_account(0)
    assert spot_market_0
    print("4: found spot market 0")

    # uncached spot market, we'll add this silently
    spot_market_1 = drift_client.get_spot_market_account(1)
    assert not spot_market_1
    print("5: did not find spot market 1")

    print("sleeping for 10 seconds")
    await asyncio.sleep(10)

    # previously uncached perp market that we should now have
    perp_market_2 = drift_client.get_perp_market_account(2)
    assert perp_market_2
    print("6: found perp market 2")

    # previously uncached spot market that we should now have
    spot_market_1 = drift_client.get_spot_market_account(1)
    assert spot_market_1
    print("7: found spot market 1")

    # entirely invalid perp market, expect rejection & no-op
    perp_market_100 = drift_client.get_perp_market_account(100)
    assert not perp_market_100
    print("8: expecting perp market 100 to be no-op")

    # entirely invalid perp market, expect rejection & no-op
    spot_market_100 = drift_client.get_spot_market_account(100)
    assert not spot_market_100
    print("9: expecting spot market 100 to be no-op")

    # cached perp oracle
    oracle_price_perp_0 = drift_client.get_oracle_price_data_for_perp_market(0)
    assert oracle_price_perp_0
    print("10: found oracle price perp 0")

    # cached perp oracle
    oracle_price_perp_1 = drift_client.get_oracle_price_data_for_perp_market(1)
    assert oracle_price_perp_1
    print("11: found oracle price perp 1")

    # uncached perp oracle, we'll add the oracle and the corresponding perp market silently
    oracle_price_perp_2 = drift_client.get_oracle_price_data_for_perp_market(9)
    assert not oracle_price_perp_2
    print("12: did not find oracle price perp 9")

    # cached spot oracle
    oracle_price_spot_0 = drift_client.get_oracle_price_data_for_spot_market(0)
    assert oracle_price_spot_0
    print("13: found oracle price spot 0")

    # uncached spot oracle, we'll add the oracle and the corresponding spot market silently
    oracle_price_spot_1 = drift_client.get_oracle_price_data_for_spot_market(5)
    assert not oracle_price_spot_1
    print("14: did not find oracle price spot 5")

    print("sleeping for 10 seconds")
    await asyncio.sleep(10)

    # previously uncached oracle that we should now have
    oracle_price_perp_2 = drift_client.get_oracle_price_data_for_perp_market(9)
    assert oracle_price_perp_2
    print("15: found oracle price perp 9")

    # previously uncached oracle that we should now have
    oracle_price_spot_1 = drift_client.get_oracle_price_data_for_spot_market(5)
    assert oracle_price_spot_1
    print("16: found oracle price spot 5")

    # perp market added with the oracle that we should now have
    perp_market_9 = drift_client.get_perp_market_account(9)
    assert perp_market_9
    print("17: found perp market 9")

    # spot market added with the oracle that we should now have
    spot_market_5 = drift_client.get_spot_market_account(5)
    assert spot_market_5
    print("18: found spot market 5")

    # make sure invalid perp was no-op
    perp_market_100 = drift_client.get_perp_market_account(100)
    assert not perp_market_100
    print("19: perp market 100 was no-op")

    # make sure invalid spot was no-op
    spot_market_100 = drift_client.get_spot_market_account(100)
    assert not spot_market_100
    print("20: spot market 100 was no-op")
