from typing import Union

from driftpy.accounts import *
from driftpy.types import OraclePriceData


def get_signed_token_amount(amount, balance_type):
    return amount if is_variant(balance_type, "Deposit") else -abs(amount)


def get_token_amount(
    balance: int, spot_market: SpotMarketAccount, balance_type: SpotBalanceType
) -> int:
    percision_decrease = 10 ** (19 - spot_market.decimals)

    cumm_interest = (
        spot_market.cumulative_deposit_interest
        if is_variant(balance_type, "Deposit")
        else spot_market.cumulative_borrow_interest
    )

    return balance * cumm_interest // percision_decrease


def get_token_value(
    amount, spot_decimals, oracle_price_data: Union[OraclePriceData, int]
):
    precision_decrease = 10**spot_decimals
    if isinstance(oracle_price_data, OraclePriceData):
        return amount * oracle_price_data.price // precision_decrease
    else:
        return amount * oracle_price_data // precision_decrease


def cast_to_spot_precision(
    amount: Union[float, int], spot_market: SpotMarketAccount
) -> int:
    precision = 10**spot_market.decimals
    return int(amount * precision)
