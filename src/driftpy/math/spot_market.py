from driftpy.constants.numeric_constants import *
from driftpy.types import *
from driftpy.accounts import *
from driftpy.math.oracle import *


def get_signed_token_amount(amount, balance_type):
    match str(balance_type):
        case "SpotBalanceType.Deposit()":
            return amount
        case "SpotBalanceType.Borrow()":
            return -abs(amount)
        case _:
            raise Exception(f"Invalid balance type: {balance_type}")


def get_token_amount(
    balance: int, spot_market: SpotMarket, balance_type: SpotBalanceType
) -> int:
    percision_decrease = 10 ** (19 - spot_market.decimals)

    match str(balance_type):
        case "SpotBalanceType.Deposit()":
            cumm_interest = spot_market.cumulative_deposit_interest
        case "SpotBalanceType.Borrow()":
            cumm_interest = spot_market.cumulative_borrow_interest
        case _:
            raise Exception(f"Invalid balance type: {balance_type}")

    return balance * cumm_interest / percision_decrease


def get_token_value(amount, spot_decimals, oracle_data: OracleData):
    precision_decrease = 10 ** spot_decimals
    return amount * oracle_data.price / precision_decrease
