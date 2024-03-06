from driftpy.drift_user import DriftUser
from driftpy.types import is_variant
from driftpy.math.perp_position import has_open_orders


def is_user_bankrupt(user: DriftUser):
    user_account = user.get_user_account()
    has_liability = False
    for position in user_account.spot_positions:
        if position.scaled_balance > 0:
            if is_variant(position.balance_type, "Deposit"):
                return False
            if is_variant(position.balance_type, "Borrow"):
                has_liability = True

    for position in user_account.perp_positions:
        if (
            position.base_asset_amount != 0
            or position.quote_asset_amount > 0
            or has_open_orders(position)
            or position.lp_shares > 0
        ):
            return False

        if position.quote_asset_amount < 0:
            has_liability = True

    return has_liability
