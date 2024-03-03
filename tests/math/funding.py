from pytest import mark
from copy import deepcopy

from driftpy.constants.numeric_constants import *
from driftpy.types import *
from driftpy.math.funding import calculate_long_short_funding_and_live_twaps

from dlob_test_constants import mock_perp_markets, mock_spot_markets


@mark.asyncio
async def test_predicted_funding_rate_mock1():
    print()
    perp_markets = deepcopy(mock_perp_markets)
    market = perp_markets[0]
    market.status = MarketStatus.Active()

    now = 1_688_878_353

    market.amm.funding_period = 3_600
    market.amm.last_funding_rate_ts = 1_688_860_817

    current_mark_price = 1.9843 * PRICE_PRECISION
    oracle_price_data = OraclePriceData(
        price=(1.9535 * PRICE_PRECISION),
        slot=0,
        confidence=1,
        twap=1,
        twap_confidence=1,
        has_sufficient_number_of_data_points=True,
    )

    market.amm.historical_oracle_data.last_oracle_price = 1.9535 * PRICE_PRECISION
    market.amm.last_mark_price_twap = 1.945594 * PRICE_PRECISION
    market.amm.last_bid_price_twap = 1.941629 * PRICE_PRECISION
    market.amm.last_ask_price_twap = 1.94956 * PRICE_PRECISION
    market.amm.historical_oracle_data.last_oracle_price_twap = (
        1.942449 * PRICE_PRECISION
    )
    market.amm.last_mark_price_twap_ts = 1_688_877_729
    market.amm.historical_oracle_data.last_oracle_price_twap_ts = 1_688_878_333

    mtl, otl, est1, est2 = await calculate_long_short_funding_and_live_twaps(
        market, oracle_price_data, current_mark_price, now
    )

    print(f"mtl: {mtl}")
    print(f"otl: {otl}")
    print(f"est1: {est1}")
    print(f"est2: {est2}")

    assert mtl == 1_949_826
    assert otl == 1_942_510
    assert est1 == 16_525
    assert est1 == est2


@mark.asyncio
async def test_predicted_funding_rate_mock2():
    print()
    perp_markets = deepcopy(mock_perp_markets)
    market = perp_markets[0]
    market.status = MarketStatus.Active()

    now = 1_688_881_915

    market.amm.funding_period = 3_600
    market.amm.last_funding_rate_ts = 1_688_864_415

    current_mark_price = 1.2242 * PRICE_PRECISION
    oracle_price_data = OraclePriceData(
        price=(1.224 * PRICE_PRECISION),
        slot=0,
        confidence=1,
        twap=1,
        twap_confidence=1,
        has_sufficient_number_of_data_points=True,
    )

    market.amm.historical_oracle_data.last_oracle_price = 1.9535 * PRICE_PRECISION
    market.amm.last_mark_price_twap = 1.218363 * PRICE_PRECISION
    market.amm.last_bid_price_twap = 1.218363 * PRICE_PRECISION
    market.amm.last_ask_price_twap = 1.218364 * PRICE_PRECISION
    market.amm.historical_oracle_data.last_oracle_price_twap = (
        1.220964 * PRICE_PRECISION
    )
    market.amm.last_mark_price_twap_ts = 1_688_878_815
    market.amm.historical_oracle_data.last_oracle_price_twap_ts = 1_688_879_991

    mtl, otl, est1, est2 = await calculate_long_short_funding_and_live_twaps(
        market, oracle_price_data, current_mark_price, now
    )

    print(f"mtl: {mtl}")
    print(f"otl: {otl}")
    print(f"est1: {est1}")
    print(f"est2: {est2}")

    assert mtl == 1_222_131
    assert otl == 1_222_586
    assert est1 == -719
    assert est1 == est2


@mark.asyncio
async def test_predicted_funding_rate_mock_clamp():
    print()
    perp_markets = deepcopy(mock_perp_markets)
    market = perp_markets[0]
    market.status = MarketStatus.Active()

    now = 1_688_881_915

    market.amm.funding_period = 3_600
    market.amm.last_funding_rate_ts = 1_688_864_415

    current_mark_price = 1.2242 * PRICE_PRECISION
    oracle_price_data = OraclePriceData(
        price=(1.924 * PRICE_PRECISION),
        slot=0,
        confidence=1,
        twap=1,
        twap_confidence=1,
        has_sufficient_number_of_data_points=True,
    )

    market.amm.historical_oracle_data.last_oracle_price = 1.9535 * PRICE_PRECISION
    market.amm.last_mark_price_twap = 1.218363 * PRICE_PRECISION
    market.amm.last_bid_price_twap = 1.218363 * PRICE_PRECISION
    market.amm.last_ask_price_twap = 1.218364 * PRICE_PRECISION
    market.amm.historical_oracle_data.last_oracle_price_twap = (
        1.820964 * PRICE_PRECISION
    )
    market.amm.last_mark_price_twap_ts = 1_688_878_815
    market.amm.historical_oracle_data.last_oracle_price_twap_ts = 1_688_879_991

    market.contract_tier = ContractTier.A()

    mtl, otl, est1, est2 = await calculate_long_short_funding_and_live_twaps(
        market, oracle_price_data, current_mark_price, now
    )

    print(f"mtl: {mtl}")
    print(f"otl: {otl}")
    print(f"est1: {est1}")
    print(f"est2: {est2}")

    assert mtl == 1_680_634
    assert otl == 1_876_031
    assert est1 == -126_261
    assert est1 == est2

    market.contract_tier = ContractTier.C()

    mtl, otl, est1, est2 = await calculate_long_short_funding_and_live_twaps(
        market, oracle_price_data, current_mark_price, now
    )

    print(f"mtl: {mtl}")
    print(f"otl: {otl}")
    print(f"est1: {est1}")
    print(f"est2: {est2}")

    assert mtl == 1_680_634
    assert otl == 1_876_031
    assert est1 == -208_332
    assert est1 == est2

    market.contract_tier = ContractTier.Speculative()

    mtl, otl, est1, est2 = await calculate_long_short_funding_and_live_twaps(
        market, oracle_price_data, current_mark_price, now
    )

    print(f"mtl: {mtl}")
    print(f"otl: {otl}")
    print(f"est1: {est1}")
    print(f"est2: {est2}")

    assert mtl == 1_680_634
    assert otl == 1_876_031
    assert est1 == -416_666
    assert est1 == est2
