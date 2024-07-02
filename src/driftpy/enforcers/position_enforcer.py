from typing import Union
from driftpy.types import (
    OrderParams,
    SpotPosition,
    PerpPosition,
    MarketType,
    UserAccount,
    is_variant,
)


class PositionEnforcer:
    def __init__(self):
        pass

    def set_and_check_order_params(
        self, expected_size: int, order_params: OrderParams, user: UserAccount
    ) -> OrderParams:
        size_adjustment = self._get_size_adjustment(
            expected_size, order_params.market_index, order_params.market_type, user
        )
        order_params.base_asset_amount = max(
            order_params.base_asset_amount + size_adjustment, 0
        )
        if order_params.base_asset_amount == 0:
            print("WARNING: PositionEnforcer has reduced order size to ZERO.")
        return order_params

    def _get_size_adjustment(
        self,
        expected_size: int,
        market_index: int,
        market_type: MarketType,
        user: UserAccount,
    ) -> int:
        position: Union[SpotPosition, PerpPosition]
        if is_variant(market_type, "Perp"):
            position = next(
                (
                    pos
                    for pos in user.perp_positions
                    if pos.market_index == market_index
                ),
                None,
            )
            if position is None:
                raise Exception(
                    f"Position market_index: {market_index} market_type: {market_type} not found"
                )

            difference = position.base_asset_amount - expected_size
            return difference * -1  # positive if too short, negative if too long
        else:
            position = next(
                (
                    pos
                    for pos in user.spot_positions
                    if pos.market_index == market_index
                ),
                None,
            )
            if position is None:
                raise Exception(
                    f"Position market_index: {market_index} market_type: {market_type} not found"
                )

            difference = position.scaled_balance - expected_size
            return difference * -1  # positive if too short, negative if too long
