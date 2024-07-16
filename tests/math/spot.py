import math
from pytest import mark
from copy import deepcopy

from driftpy.math.margin import calculate_size_premium_liability_weight
from driftpy.constants.numeric_constants import *

from tests.dlob_test_constants import mock_spot_markets
from driftpy.math.spot_balance import (
    calculate_borrow_rate,
    calculate_deposit_rate,
    calculate_spot_market_borrow_capacity,
)


@mark.asyncio
async def test_size_prem_imf():
    maintenance_liability_weight = 1.1 * TEN_THOUSAND

    weight1 = calculate_size_premium_liability_weight(
        200_000 * ONE_BILLION, 0, maintenance_liability_weight, TEN_THOUSAND
    )

    assert weight1 == maintenance_liability_weight

    weight2 = calculate_size_premium_liability_weight(
        200_000 * ONE_BILLION,
        int(0.00055 * ONE_MILLION),
        maintenance_liability_weight,
        TEN_THOUSAND,
    )

    assert weight2 == 11_259
    assert weight2 > weight1

    weight3 = calculate_size_premium_liability_weight(
        TEN_THOUSAND * ONE_BILLION,
        int(0.003 * ONE_MILLION),
        maintenance_liability_weight,
        TEN_THOUSAND,
    )

    assert weight3 == 11_800
    assert weight3 > weight2

    weight4 = calculate_size_premium_liability_weight(
        ONE_HUNDRED_THOUSAND * ONE_BILLION,
        int(0.003 * ONE_MILLION),
        maintenance_liability_weight,
        TEN_THOUSAND,
    )

    assert weight4 == 18_286
    assert weight4 > weight3


@mark.asyncio
async def test_base_borrow_capacity():
    spot_market = deepcopy(mock_spot_markets[0])

    spot_market.max_borrow_rate = 1_000_000
    spot_market.optimal_borrow_rate = 100_000
    spot_market.optimal_utilization = 700_000

    spot_market.decimals = 9
    spot_market.cumulative_borrow_interest = SPOT_CUMULATIVE_INTEREST_PRECISION
    spot_market.cumulative_deposit_interest = SPOT_CUMULATIVE_INTEREST_PRECISION

    token_amount = 100_000

    # no borrows
    spot_market.deposit_balance = token_amount * ONE_BILLION
    spot_market.borrow_balance = 0

    _, remaining_capacity = calculate_spot_market_borrow_capacity(
        spot_market, 2_000_000
    )
    assert remaining_capacity > spot_market.deposit_balance

    _, remaining_capacity = calculate_spot_market_borrow_capacity(
        spot_market, 1_000_000
    )
    assert remaining_capacity == spot_market.deposit_balance

    _, remaining_capacity = calculate_spot_market_borrow_capacity(spot_market, 100_000)
    rhs = (spot_market.deposit_balance * 7) // 10
    assert remaining_capacity == rhs

    _, remaining_capacity = calculate_spot_market_borrow_capacity(spot_market, 810_000)
    assert remaining_capacity < spot_market.deposit_balance
    assert remaining_capacity > rhs
    assert remaining_capacity == 93_666_600_000_000

    _, remaining_capacity = calculate_spot_market_borrow_capacity(spot_market, 50_000)
    assert remaining_capacity == (rhs // 2)

    _, remaining_capacity = calculate_spot_market_borrow_capacity(spot_market, 24_900)
    assert remaining_capacity < (rhs // 4)
    assert remaining_capacity == 17_430_000_000_000

    _, remaining_capacity = calculate_spot_market_borrow_capacity(spot_market, 1)
    assert remaining_capacity == 700_000_000


@mark.asyncio
async def test_complex_borrow_capacity():
    spot_market = deepcopy(mock_spot_markets[0])

    spot_market.max_borrow_rate = 1_000_000
    spot_market.optimal_borrow_rate = 70_000
    spot_market.optimal_utilization = 700_000

    spot_market.decimals = 9
    spot_market.cumulative_deposit_interest = int(
        1.0154217042 * SPOT_CUMULATIVE_INTEREST_PRECISION
    )
    spot_market.cumulative_borrow_interest = int(
        1.0417153549 * SPOT_CUMULATIVE_INTEREST_PRECISION
    )

    spot_market.deposit_balance = int(88522.734106451 * ONE_BILLION)
    spot_market.borrow_balance = int(7089.91675884 * ONE_BILLION)

    _, remaining_capacity = calculate_spot_market_borrow_capacity(
        spot_market, 2_000_000
    )
    assert remaining_capacity == 111_498_270_939_007

    _, max_amount = calculate_spot_market_borrow_capacity(spot_market, 1_000_000)
    assert max_amount == 82_502_230_374_168

    _, opt_amount = calculate_spot_market_borrow_capacity(spot_market, 70_000)
    assert opt_amount == 55_535_858_716_123

    _, remaining_capacity = calculate_spot_market_borrow_capacity(spot_market, 810_000)
    assert remaining_capacity < max_amount
    assert remaining_capacity > opt_amount
    assert remaining_capacity == 76_992_910_756_523

    _, remaining_capacity = calculate_spot_market_borrow_capacity(spot_market, 50_000)
    assert remaining_capacity == 37_558_277_610_760

    _, remaining_capacity = calculate_spot_market_borrow_capacity(spot_market, 24_900)
    assert remaining_capacity == 14_996_413_323_529

    _, remaining_capacity = calculate_spot_market_borrow_capacity(spot_market, 4_900)
    assert remaining_capacity == 0

    _, remaining_capacity = calculate_spot_market_borrow_capacity(spot_market, 1)
    assert remaining_capacity == 0


@mark.asyncio
async def test_borrow_rates():
    spot_market = deepcopy(mock_spot_markets[0])

    spot_market.max_borrow_rate = 1_000_000
    spot_market.optimal_borrow_rate = 70_000
    spot_market.optimal_utilization = 700_000

    spot_market.decimals = 9
    spot_market.cumulative_deposit_interest = int(
        1.0154217042 * SPOT_CUMULATIVE_INTEREST_PRECISION
    )
    spot_market.cumulative_borrow_interest = int(
        1.0417153549 * SPOT_CUMULATIVE_INTEREST_PRECISION
    )

    spot_market.deposit_balance = int(88522.734106451 * ONE_BILLION)
    spot_market.borrow_balance = int(17089.91675884 * ONE_BILLION)

    no_delta_deposit_rate = calculate_deposit_rate(spot_market)
    assert no_delta_deposit_rate == 3_922

    no_delta_borrow_rate = calculate_borrow_rate(spot_market)
    assert no_delta_borrow_rate == 19_805

    # update deposits
    spot_market.deposit_balance = int((88522.734106451 + 9848.12512736) * ONE_BILLION)

    no_delta_deposit_rate_2 = calculate_deposit_rate(spot_market)
    assert no_delta_deposit_rate_2 == 3_176

    no_delta_borrow_rate_2 = calculate_borrow_rate(spot_market)
    assert no_delta_borrow_rate_2 == 17_822

    # update deposits
    spot_market.deposit_balance = int(88522.734106451 * ONE_BILLION)

    delta_deposit_rate = calculate_deposit_rate(spot_market, (10_000 * ONE_BILLION))
    assert delta_deposit_rate == 3_176

    delta_borrow_rate = calculate_borrow_rate(spot_market, (10_000 * ONE_BILLION))
    assert delta_borrow_rate == 17_822

    delta_deposit_rate_2 = calculate_deposit_rate(spot_market, (-1_000 * ONE_BILLION))
    assert delta_deposit_rate_2 == 4_375

    delta_borrow_rate_2 = calculate_borrow_rate(spot_market, (-1_000 * ONE_BILLION))
    assert delta_borrow_rate_2 == 20_918
