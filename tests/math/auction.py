from pytest import mark

from driftpy.math.auction import derive_oracle_auction_params
from driftpy.types import PositionDirection
from driftpy.constants.numeric_constants import PRICE_PRECISION


@mark.asyncio
async def test_drive_oracle_auction_params():
    oracle_price = 100 * PRICE_PRECISION
    auction_start_price = 90 * PRICE_PRECISION
    auction_end_price = 110 * PRICE_PRECISION
    limit_price = 120 * PRICE_PRECISION

    oracle_order_params = derive_oracle_auction_params(
        PositionDirection.Long(),
        oracle_price,
        auction_start_price,
        auction_end_price,
        limit_price,
    )

    assert oracle_order_params[0] == -10 * PRICE_PRECISION
    assert oracle_order_params[1] == 10 * PRICE_PRECISION
    assert oracle_order_params[2] == 20 * PRICE_PRECISION

    oracle_order_params = derive_oracle_auction_params(
        PositionDirection.Long(), oracle_price, oracle_price, oracle_price, oracle_price
    )

    assert oracle_order_params[0] == 0
    assert oracle_order_params[1] == 0
    assert oracle_order_params[2] == 1

    oracle_price = 100 * PRICE_PRECISION
    auction_start_price = 110 * PRICE_PRECISION
    auction_end_price = 90 * PRICE_PRECISION
    limit_price = 80 * PRICE_PRECISION

    oracle_order_params = derive_oracle_auction_params(
        PositionDirection.Short(),
        oracle_price,
        auction_start_price,
        auction_end_price,
        limit_price,
    )

    assert oracle_order_params[0] == 10 * PRICE_PRECISION
    assert oracle_order_params[1] == -10 * PRICE_PRECISION
    assert oracle_order_params[2] == -20 * PRICE_PRECISION

    oracle_order_params = derive_oracle_auction_params(
        PositionDirection.Short(),
        oracle_price,
        oracle_price,
        oracle_price,
        oracle_price,
    )

    assert oracle_order_params[0] == 0
    assert oracle_order_params[1] == 0
    assert oracle_order_params[2] == -1
