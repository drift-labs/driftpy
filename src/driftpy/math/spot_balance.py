from driftpy.oracles.strict_oracle_price import StrictOraclePrice


def get_strict_token_value(
    token_amount: int, spot_decimals: int, strict_oracle_price: StrictOraclePrice
) -> int:
    if token_amount == 0:
        return 0

    if token_amount > 0:
        price = strict_oracle_price.min()
    else:
        price = strict_oracle_price.max()

    precision_decrease = 10**spot_decimals

    return (token_amount * price) // precision_decrease
