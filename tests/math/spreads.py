import time
from copy import deepcopy

from pytest import mark

from driftpy.constants.numeric_constants import (
    AMM_RESERVE_PRECISION,
    ONE_MILLION,
    PEG_PRECISION,
    PERCENTAGE_PRECISION,
    PRICE_PRECISION,
    QUOTE_PRECISION,
)
from driftpy.math.amm import (
    calculate_inventory_liquidity_ratio,
    calculate_inventory_scale,
    calculate_price,
    calculate_reference_price_offset,
    calculate_spread_bn,
    calculate_spread_reserves,
)
from driftpy.math.oracles import (
    calculate_live_oracle_std,
    calculate_live_oracle_twap,
    get_new_oracle_conf_pct,
    is_oracle_valid,
)
from driftpy.math.utils import sig_num
from driftpy.types import (
    OracleGuardRails,
    OraclePriceData,
    PriceDivergenceGuardRails,
    ValidityGuardRails,
)
from tests.dlob_test_constants import mock_perp_markets


@mark.asyncio
async def test_spread_maths():
    iscale = calculate_inventory_scale(
        0,
        AMM_RESERVE_PRECISION,
        AMM_RESERVE_PRECISION // 2,
        (AMM_RESERVE_PRECISION * 3) // 2,
        250.0,
        30_000.0,
    )
    assert iscale == 1

    iscale = calculate_inventory_scale(
        1,
        AMM_RESERVE_PRECISION,
        AMM_RESERVE_PRECISION // 2,
        (AMM_RESERVE_PRECISION * 3) // 2,
        250.0,
        30_000.0,
    )
    assert iscale == 1

    baa = 1_000
    iscale = calculate_inventory_scale(
        baa,
        AMM_RESERVE_PRECISION + baa,
        AMM_RESERVE_PRECISION // 2,
        (AMM_RESERVE_PRECISION * 3) // 2,
        250.0,
        30_000.0,
    )
    assert iscale == 1.00024

    baa = 100_000
    iscale = calculate_inventory_scale(
        baa,
        AMM_RESERVE_PRECISION + baa,
        AMM_RESERVE_PRECISION // 2,
        (AMM_RESERVE_PRECISION * 3) // 2,
        250.0,
        30_000.0,
    )
    assert iscale == 1.024

    baa = 1_000_000
    iscale = calculate_inventory_scale(
        baa,
        AMM_RESERVE_PRECISION + baa,
        AMM_RESERVE_PRECISION // 2,
        (AMM_RESERVE_PRECISION * 3) // 2,
        250.0,
        30_000.0,
    )
    assert iscale == 1.24048

    baa = 10_000_000
    iscale = calculate_inventory_scale(
        baa,
        AMM_RESERVE_PRECISION + baa,
        AMM_RESERVE_PRECISION // 2,
        (AMM_RESERVE_PRECISION * 3) // 2,
        250.0,
        30_000.0,
    )
    assert iscale == 3.44896

    baa = 50_000_000
    iscale = calculate_inventory_scale(
        baa,
        AMM_RESERVE_PRECISION + baa,
        AMM_RESERVE_PRECISION // 2,
        (AMM_RESERVE_PRECISION * 3) // 2,
        250.0,
        30_000.0,
    )
    assert iscale == 14.33332

    baa = AMM_RESERVE_PRECISION // 2
    iscale = calculate_inventory_scale(
        baa,
        AMM_RESERVE_PRECISION + baa,
        AMM_RESERVE_PRECISION // 2,
        (AMM_RESERVE_PRECISION * 3) // 2,
        250.0,
        30_000.0,
    )
    assert iscale == 120

    baa = AMM_RESERVE_PRECISION // 4
    iscale = calculate_inventory_scale(
        baa,
        AMM_RESERVE_PRECISION + baa,
        AMM_RESERVE_PRECISION // 2,
        (AMM_RESERVE_PRECISION * 3) // 2,
        250.0,
        30_000.0 * 2.0,
    )
    assert iscale == (120 * 2)

    baa = AMM_RESERVE_PRECISION // 5
    iscale = calculate_inventory_scale(
        baa,
        AMM_RESERVE_PRECISION + baa,
        AMM_RESERVE_PRECISION // 2,
        (AMM_RESERVE_PRECISION * 3) // 2,
        250.0,
        30_000.0 * 2.0,
    )
    assert iscale == 160.99984

    baa = 855_329_058
    iscale = calculate_inventory_scale(
        baa,
        AMM_RESERVE_PRECISION + baa,
        AMM_RESERVE_PRECISION // 2,
        AMM_RESERVE_PRECISION,
        250.0,
        30_000.0,
    )
    assert iscale == 120
    assert iscale * 250 == 30_000

    iscale = calculate_inventory_scale(
        baa,
        AMM_RESERVE_PRECISION + baa,
        AMM_RESERVE_PRECISION // 2,
        (AMM_RESERVE_PRECISION * 3) // 2,
        250.0,
        30_000.0,
    )
    assert iscale == 120
    assert iscale * 250 == 30_000

    baa = -855_329_058
    iscale = calculate_inventory_scale(
        baa,
        AMM_RESERVE_PRECISION + baa,
        AMM_RESERVE_PRECISION // 2,
        (AMM_RESERVE_PRECISION * 3) // 2,
        250.0,
        30_000.0,
    )
    assert iscale == 120
    assert iscale * 250 == 30_000

    iscale = calculate_inventory_scale(
        30_228_000_000_000_000,
        2_496_788_386_034_912_600,
        2_443_167_585_342_470_000,
        2_545_411_471_321_696_000,
        3_500.0,
        100_000.0,
    )
    assert iscale == 18.762285
    assert (iscale * 3500.0) / ONE_MILLION == 0.06566799749999999


@mark.asyncio
async def test_various_spreads():
    base_spread = int(0.025 * ONE_MILLION)
    last_oracle_reserve_price_spread_pct = 0
    last_oracle_conf_pct = 0
    max_spread = int(0.03 * ONE_MILLION)
    quote_asset_reserve = AMM_RESERVE_PRECISION * 100
    terminal_quote_asset_reserve = AMM_RESERVE_PRECISION * 100
    peg_multiplier = int(13.455 * PEG_PRECISION)
    base_asset_amount_with_amm = 0
    reserve_price = int(13.455 * PRICE_PRECISION)
    total_fee_minus_distributions = 1
    net_revenue_since_last_funding = 2 * QUOTE_PRECISION
    base_asset_reserve = AMM_RESERVE_PRECISION * 100
    min_base_asset_reserve = AMM_RESERVE_PRECISION * 90
    max_base_asset_reserve = AMM_RESERVE_PRECISION * 110
    mark_std = int(0.45 * PRICE_PRECISION)
    oracle_std = int(0.55 * PRICE_PRECISION)
    long_intensity = QUOTE_PRECISION * 20
    short_intensity = QUOTE_PRECISION * 2
    volume_24h = QUOTE_PRECISION * 25

    spreads = calculate_spread_bn(
        base_spread,
        last_oracle_reserve_price_spread_pct,
        last_oracle_conf_pct,
        max_spread,
        quote_asset_reserve,
        terminal_quote_asset_reserve,
        peg_multiplier,
        base_asset_amount_with_amm,
        reserve_price,
        total_fee_minus_distributions,
        net_revenue_since_last_funding,
        base_asset_reserve,
        min_base_asset_reserve,
        max_base_asset_reserve,
        mark_std,
        oracle_std,
        long_intensity,
        short_intensity,
        volume_24h,
    )

    long_spread_1 = spreads[0]
    short_spread_1 = spreads[1]

    spread_terms_1 = calculate_spread_bn(
        base_spread,
        last_oracle_reserve_price_spread_pct,
        last_oracle_conf_pct,
        max_spread,
        quote_asset_reserve,
        terminal_quote_asset_reserve,
        peg_multiplier,
        base_asset_amount_with_amm,
        reserve_price,
        total_fee_minus_distributions,
        net_revenue_since_last_funding,
        base_asset_reserve,
        min_base_asset_reserve,
        max_base_asset_reserve,
        mark_std,
        oracle_std,
        long_intensity,
        short_intensity,
        volume_24h,
        True,
    )

    assert long_spread_1 == 14_864
    assert short_spread_1 == 12_500
    assert long_spread_1 == spread_terms_1["long_spread"]
    assert short_spread_1 == spread_terms_1["short_spread"]

    spread_terms_2 = calculate_spread_bn(
        300,
        0,
        484,
        47_500,
        923_807_816_209_694,
        925_117_623_772_584,
        13_731_157,
        -1_314_027_016_625,
        13_667_686,
        115_876_379_475,
        91_316_628,
        928_097_825_691_666,
        907_979_542_352_912,
        945_977_491_145_601,
        161_188,
        1_459_632_439,
        12_358_265_776,
        72_230_366_233,
        432_067_603_632,
        True,
    )

    assert spread_terms_2["effective_leverage_capped"] >= 1.0002
    assert spread_terms_2["inventory_spread_scale"] == 1.73493
    assert spread_terms_2["long_spread"] == 4_262
    assert spread_terms_2["short_spread"] == 43_238
    assert spread_terms_2["long_spread"] + spread_terms_2["short_spread"] == 47_500


@mark.asyncio
async def test_corner_case_spreads():
    spread_terms = calculate_spread_bn(
        1_000,
        5_555,
        1_131,
        20_000,
        1_009_967_115_003_047,
        1_009_811_402_660_255,
        13_460_124,
        15_328_930_153,
        13_667_686,
        1_235_066_973,
        88_540_713,
        994_097_717_724_176,
        974_077_854_655_784,
        1_014_841_945_381_208,
        103_320,
        59_975,
        768_323_534,
        243_875_031,
        130_017_761_029,
        True,
    )

    assert spread_terms["effective_leverage_capped"] <= 1.000001
    assert spread_terms["inventory_spread_scale"] == 1.0306
    assert spread_terms["long_spread"] == 515
    assert spread_terms["short_spread"] == 5_668

    base_spread = 5_000
    last_oracle_reserve_price_spread_pct = -262_785
    last_oracle_conf_pct = 1_359
    max_spread = 29_500
    quote_asset_reserve = 50_933_655_038_273_508_156
    terminal_quote_asset_reserve = 50_933_588_428_309_274_920
    peg_multiplier = 4
    base_asset_amount_with_amm = 306_519_581
    total_fee_minus_distributions = -29_523_583_393
    net_revenue_since_last_funding = -141_830_281
    base_asset_reserve = 234_381_482_764_434
    min_base_asset_reserve = 194_169_322_578_092
    max_base_asset_reserve = 282_922_257_844_734
    mark_std = 237_945
    oracle_std = 8_086
    long_intensity = 162_204
    short_intensity = 2_797_331_131
    volume_24h = 91_370_028_405

    reserve_price = calculate_price(
        base_asset_reserve, quote_asset_reserve, peg_multiplier
    )
    assert reserve_price == 869_243

    reserve_price_mod = calculate_price(
        base_asset_reserve, quote_asset_reserve, peg_multiplier + 1
    )
    assert reserve_price_mod == 1_086_554

    sui_terms = calculate_spread_bn(
        base_spread,
        last_oracle_reserve_price_spread_pct,
        last_oracle_conf_pct,
        max_spread,
        quote_asset_reserve,
        terminal_quote_asset_reserve,
        peg_multiplier,
        base_asset_amount_with_amm,
        reserve_price,
        total_fee_minus_distributions,
        net_revenue_since_last_funding,
        base_asset_reserve,
        min_base_asset_reserve,
        max_base_asset_reserve,
        mark_std,
        oracle_std,
        long_intensity,
        short_intensity,
        volume_24h,
        True,
    )

    assert sui_terms["effective_leverage_capped"] <= 1.000001
    assert sui_terms["inventory_spread_scale"] == 1.00007
    assert sui_terms["long_spread"] == 259_073
    assert sui_terms["short_spread"] == 3_712


@mark.asyncio
async def test_spread_reserves_with_offset():
    perp_markets = deepcopy(mock_perp_markets)
    market = perp_markets[0]
    amm = market.amm

    now = int(time.time())

    oracle_price_data = OraclePriceData(
        int(13.553 * PRICE_PRECISION),
        69,
        1,
        0,
        0,
        True,  # kek
    )

    bid_reserves, ask_reserves = calculate_spread_reserves(amm, oracle_price_data, now)

    assert bid_reserves[0] == 1_000_000_000
    assert bid_reserves[1] == 12_000_000_000
    assert ask_reserves[0] == 1_000_000_000
    assert ask_reserves[1] == 12_000_000_000

    amm.base_asset_reserve = 1_000_000_000
    amm.quote_asset_reserve = 1_000_000_000
    amm.sqrt_k = 1_000_000_000

    amm.base_asset_amount_with_amm = 0
    amm.peg_multiplier = int(13.553 * PEG_PRECISION)
    amm.amm_jit_intensity = 200
    amm.curve_update_intensity = 200
    amm.base_spread = 2_500
    amm.max_spread = 25_000

    amm.last24h_avg_funding_rate = 7_590_328_523
    amm.last_mark_price_twap = (oracle_price_data.price / 1e6 - 0.01) * 1e6
    amm.historical_oracle_data.last_oracle_price_twap = (
        oracle_price_data.price / 1e6 + 0.015
    ) * 1e6
    amm.historical_oracle_data.last_oracle_price_twap5min = (
        oracle_price_data.price / 1e6 + 0.005
    ) * 1e6
    amm.last_mark_price_twap5min = (oracle_price_data.price / 1e6 - 0.005) * 1e6

    reserve_price = calculate_price(
        amm.base_asset_reserve, amm.quote_asset_reserve, amm.peg_multiplier
    )

    assert amm.base_asset_reserve == 1_000_000_000

    bid_reserves, ask_reserves = calculate_spread_reserves(amm, oracle_price_data, now)

    assert ask_reserves[0] == 992_125_985
    assert ask_reserves[1] == 1_007_936_507
    assert bid_reserves[0] == 1_004_629_628
    assert bid_reserves[1] == 995_391_706

    # create imbalance for reference price offset
    amm.base_asset_reserve = 1_000_000_000 * 1.1
    amm.quote_asset_reserve = 1_000_000_000 / 1.1
    amm.sqrt_k = int((amm.base_asset_reserve * amm.quote_asset_reserve) ** 0.5)
    amm.base_asset_amount_with_amm = int(1_000_000_000 * 0.1)

    lhs = amm.max_spread // 5
    rhs = (PERCENTAGE_PRECISION // 10_000) * (amm.curve_update_intensity - 100)
    max_offset = max(lhs, rhs)

    liquidity_fraction = calculate_inventory_liquidity_ratio(
        amm.base_asset_amount_with_amm,
        amm.base_asset_reserve,
        amm.min_base_asset_reserve,
        amm.max_base_asset_reserve,
    )
    full = 1_000_000
    assert liquidity_fraction == full

    sign = sig_num(
        amm.base_asset_amount_with_amm + amm.base_asset_amount_with_unsettled_lp
    )
    liquidity_fraction_signed = liquidity_fraction * sign

    reference_price_offset = calculate_reference_price_offset(
        reserve_price,
        amm.last24h_avg_funding_rate,
        liquidity_fraction_signed,
        amm.historical_oracle_data.last_oracle_price_twap5min,
        amm.last_mark_price_twap5min,
        amm.historical_oracle_data.last_oracle_price_twap,
        amm.last_mark_price_twap,
        max_offset,
    )

    assert reference_price_offset == 10_000
    assert reference_price_offset == max_offset

    bid_reserves, ask_reserves = calculate_spread_reserves(amm, oracle_price_data, now)

    assert bid_reserves[0] == 1_093_209_874
    assert bid_reserves[1] == 914_737_436
    assert ask_reserves[0] == 977_777_776
    assert ask_reserves[1] == 1_022_727_272

    bid_price = calculate_price(bid_reserves[0], bid_reserves[1], amm.peg_multiplier)

    ask_price = calculate_price(ask_reserves[0], ask_reserves[1], amm.peg_multiplier)

    assert bid_price == 11340399
    assert ask_price == 14176045

    amm.curve_update_intensity = 110

    bid_reserves, ask_reserves = calculate_spread_reserves(amm, oracle_price_data, now)

    assert bid_reserves[0] == 1093209874
    assert bid_reserves[1] == 914737436
    assert ask_reserves[0] == 977777776
    assert ask_reserves[1] == 1022727272

    bid_price_ref = calculate_price(
        bid_reserves[0], bid_reserves[1], amm.peg_multiplier
    )

    ask_price_ref = calculate_price(
        ask_reserves[0], ask_reserves[1], amm.peg_multiplier
    )

    assert bid_price_ref == 11340399
    assert ask_price_ref == 14176045

    # no ref price offset at 100
    amm.curve_update_intensity = 100

    bid_reserves, ask_reserves = calculate_spread_reserves(amm, oracle_price_data, now)

    assert bid_reserves[0] == 1_100_068_201
    assert bid_reserves[1] == 909_034_546
    assert ask_reserves[0] == 989_999_998
    assert ask_reserves[1] == 1_010_101_010

    bid_price_noref = calculate_price(
        bid_reserves[0], bid_reserves[1], amm.peg_multiplier
    )

    ask_price_noref = calculate_price(
        ask_reserves[0], ask_reserves[1], amm.peg_multiplier
    )
    # TODO: Rewrite this test?


@mark.asyncio
async def test_spread_reserves_with_negative_offset():
    perp_markets = deepcopy(mock_perp_markets)
    perp_market = perp_markets[0]
    amm = perp_market.amm

    now = int(time.time())

    oracle_price_data = OraclePriceData(
        int(13.553 * PRICE_PRECISION),
        69,
        1,
        0,
        0,
        True,  # kek
    )

    bid_reserves, ask_reserves = calculate_spread_reserves(amm, oracle_price_data, now)

    assert bid_reserves[0] == 1_000_000_000
    assert bid_reserves[1] == 12_000_000_000
    assert ask_reserves[0] == 1_000_000_000
    assert ask_reserves[1] == 12_000_000_000

    amm.base_asset_reserve = 1_000_000_000
    amm.quote_asset_reserve = 1_000_000_000
    amm.sqrt_k = 1_000_000_000

    amm.base_asset_amount_with_amm = 0
    amm.peg_multiplier = int(13.553 * PEG_PRECISION)
    amm.amm_jit_intensity = 200
    amm.curve_update_intensity = 200
    amm.base_spread = 2_500
    amm.max_spread = 25_000

    amm.last24h_avg_funding_rate = -7_590_328_523
    amm.last_mark_price_twap = (oracle_price_data.price / 1e6 + 0.01) * 1e6
    amm.historical_oracle_data.last_oracle_price_twap = (
        oracle_price_data.price / 1e6 - 0.015
    ) * 1e6
    amm.historical_oracle_data.last_oracle_price_twap5min = (
        oracle_price_data.price / 1e6 + 0.005
    ) * 1e6
    amm.last_mark_price_twap5min = (oracle_price_data.price / 1e6 - 0.005) * 1e6

    reserve_price = calculate_price(
        amm.base_asset_reserve, amm.quote_asset_reserve, amm.peg_multiplier
    )

    assert amm.base_asset_reserve == 1_000_000_000

    bid_reserves, ask_reserves = calculate_spread_reserves(amm, oracle_price_data, now)

    assert bid_reserves[0] == 1_006_289_308
    assert bid_reserves[1] == 993_750_000
    assert ask_reserves[0] == 993_788_819
    assert ask_reserves[1] == 1_006_250_000

    # create imbalance for reference price offset
    amm.base_asset_reserve = 1_000_000_000 / 1.1
    amm.quote_asset_reserve = 1_000_000_000 * 1.1
    amm.sqrt_k = int((amm.base_asset_reserve * amm.quote_asset_reserve) ** 0.5)
    amm.base_asset_amount_with_amm = int(-1_000_000_000 * 0.1)

    lhs = amm.max_spread // 5
    rhs = (PERCENTAGE_PRECISION // 10_000) * (amm.curve_update_intensity - 100)
    max_offset = max(lhs, rhs)

    liquidity_fraction = calculate_inventory_liquidity_ratio(
        amm.base_asset_amount_with_amm,
        amm.base_asset_reserve,
        amm.min_base_asset_reserve,
        amm.max_base_asset_reserve,
    )
    full = 1_000_000
    assert liquidity_fraction == full

    sign = sig_num(
        amm.base_asset_amount_with_amm + amm.base_asset_amount_with_unsettled_lp
    )
    liquidity_fraction_signed = liquidity_fraction * sign

    reference_price_offset = calculate_reference_price_offset(
        reserve_price,
        amm.last24h_avg_funding_rate,
        liquidity_fraction_signed,
        amm.historical_oracle_data.last_oracle_price_twap5min,
        amm.last_mark_price_twap5min,
        amm.historical_oracle_data.last_oracle_price_twap,
        amm.last_mark_price_twap,
        max_offset,
    )

    assert reference_price_offset == -10_000

    bid_reserves, ask_reserves = calculate_spread_reserves(amm, oracle_price_data, now)

    assert bid_reserves[0] == 1_010_101_008
    assert bid_reserves[1] == 990_000_000
    assert ask_reserves[0] == 914772725
    assert ask_reserves[1] == 1093167702

    bid_price = calculate_price(bid_reserves[0], bid_reserves[1], amm.peg_multiplier)

    ask_price = calculate_price(ask_reserves[0], ask_reserves[1], amm.peg_multiplier)

    assert bid_price == 13_283_295
    assert ask_price == 16196046

    amm.curve_update_intensity = 110

    bid_reserves, ask_reserves = calculate_spread_reserves(amm, oracle_price_data, now)

    assert bid_reserves[0] == 1010101008
    assert bid_reserves[1] == 990000000
    assert ask_reserves[0] == 914772725
    assert ask_reserves[1] == 1093167702

    bid_price_ref = calculate_price(
        bid_reserves[0], bid_reserves[1], amm.peg_multiplier
    )

    ask_price_ref = calculate_price(
        ask_reserves[0], ask_reserves[1], amm.peg_multiplier
    )

    assert bid_price_ref == 13283295
    assert ask_price_ref == 16196046

    # no ref price offset at 100
    amm.curve_update_intensity = 100

    bid_reserves, ask_reserves = calculate_spread_reserves(amm, oracle_price_data, now)

    assert bid_reserves[0] == 999_999_998
    assert bid_reserves[1] == 1_000_000_000
    assert ask_reserves[0] == 909_034_547
    assert ask_reserves[1] == 1_100_068_200

    bid_price_noref = calculate_price(
        bid_reserves[0], bid_reserves[1], amm.peg_multiplier
    )

    ask_price_noref = calculate_price(
        ask_reserves[0], ask_reserves[1], amm.peg_multiplier
    )

    assert bid_price_noref == 13_553_000
    assert ask_price_noref == 16_401_163

    rr = int(((ask_price_ref - ask_price_noref) * PERCENTAGE_PRECISION) / ask_price_ref)
    assert rr == -12664


@mark.asyncio
async def test_live_update_functions():
    perp_markets = deepcopy(mock_perp_markets)
    perp_market = perp_markets[0]
    amm = perp_market.amm

    now = time.time()
    slot = 999_999_999

    oracle_price_data = OraclePriceData(
        int(13.553 * PRICE_PRECISION), slot, 1_000, 0, 0, True
    )

    amm.oracle_std = int(0.18 * PRICE_PRECISION)
    amm.funding_period = 3_600
    amm.historical_oracle_data.last_oracle_price_twap = (
        oracle_price_data.price * 999
    ) // 1_000
    amm.historical_oracle_data.last_oracle_price_twap_ts = now - 11

    live_oracle_twap = calculate_live_oracle_twap(
        amm.historical_oracle_data, oracle_price_data, now, amm.funding_period
    )
    assert live_oracle_twap == 13_539_488

    live_oracle_std = calculate_live_oracle_std(amm, oracle_price_data, now)
    assert live_oracle_std == 192_962

    amm.last_oracle_conf_pct = 150_000
    reserve_price = int(13.553 * PRICE_PRECISION)
    new_conf_pct = get_new_oracle_conf_pct(amm, oracle_price_data, reserve_price, now)

    assert now - amm.historical_oracle_data.last_oracle_price_twap_ts > 0
    assert new_conf_pct == 135_000

    oracle_guard_rails = OracleGuardRails(
        PriceDivergenceGuardRails(
            PERCENTAGE_PRECISION // 10, PERCENTAGE_PRECISION // 10
        ),
        ValidityGuardRails(10, 60, 20_000, 5),
    )

    # good oracle
    assert is_oracle_valid(perp_market, oracle_price_data, oracle_guard_rails, slot + 5)

    # too confident
    oracle_price_data.confidence = int(13.553 * PRICE_PRECISION * 0.021)
    assert not is_oracle_valid(perp_market, oracle_price_data, oracle_guard_rails, slot)

    # not enough data points
    oracle_price_data.confidence = 1
    oracle_price_data.has_sufficient_number_of_data_points = False
    assert not is_oracle_valid(perp_market, oracle_price_data, oracle_guard_rails, slot)

    # negative oracle price
    oracle_price_data.has_sufficient_number_of_data_points = True
    oracle_price_data.price = -1 * PRICE_PRECISION
    assert not is_oracle_valid(perp_market, oracle_price_data, oracle_guard_rails, slot)

    # too delayed for amm
    oracle_price_data.price = int(13.553 * PRICE_PRECISION)
    assert not is_oracle_valid(
        perp_market, oracle_price_data, oracle_guard_rails, slot + 100
    )

    # oracle slot is stale (should be valid)
    oracle_price_data.slot += 100
    assert is_oracle_valid(perp_market, oracle_price_data, oracle_guard_rails, slot)

    # too volatile (>5x higher)
    oracle_price_data.slot = slot + 5
    oracle_price_data.price = int(113.553 * PRICE_PRECISION)
    assert not is_oracle_valid(perp_market, oracle_price_data, oracle_guard_rails, slot)

    # too volatile (>5x lower)
    oracle_price_data.price = int(0.553 * PRICE_PRECISION)
    assert not is_oracle_valid(perp_market, oracle_price_data, oracle_guard_rails, slot)
