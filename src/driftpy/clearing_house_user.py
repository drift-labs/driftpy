# from turtle import pos
from driftpy.clearing_house import ClearingHouse
from solana.publickey import PublicKey
from typing import cast
from driftpy.types import (
    # PositionDirection,
    # StateAccount,
    # MarketsAccount,
    # FundingPaymentHistoryAccount,
    # FundingRateHistoryAccount,
    # TradeHistoryAccount,
    # LiquidationHistoryAccount,
    # DepositHistoryAccount,
    # ExtendedCurveHistoryAccount,
    # User,
    UserPositions,
    MarketPosition,
)

from driftpy.math.positions import (
    calculate_base_asset_value,
    calculate_position_pnl,
)


class ClearingHouseUser:
    """This class is the main way to interact with Drift Protocol.

    It allows you to subscribe to the various accounts where the Market's state is
    stored, as well as: opening positions, liquidating, settling funding, depositing &
    withdrawing, and more.

    The default way to construct a ClearingHouse instance is using the
    [create][driftpy.clearing_house.ClearingHouse.create] method.
    """

    def __init__(self, clearing_house: ClearingHouse, authority: PublicKey):
        """Initialize the ClearingHouse object.

        Note: you probably want to use
        [create][driftpy.clearing_house.ClearingHouse.create]
        instead of this method.

        Args:
            clearing_house: The Drift ClearingHouse object.
            authority: user authority to focus on
        """
        self.clearing_house = clearing_house
        self.authority = authority

    async def get_user_account(self):
        user_account = await self.clearing_house.get_user_account()
        return user_account

    async def get_user_positions_account(self) -> UserPositions:
        user_account = self.get_user_account()
        positions = cast(
            UserPositions,
            await self.clearing_house.program.account["UserPositions"].fetch(
                user_account.positions
            ),
        )

        return positions

    async def get_user_position(self, market_index) -> MarketPosition:
        positions = await self.get_user_positions_account()
        for position in positions:
            if position.market_index == market_index:
                return position
        return MarketPosition(
            market_index, 0, 0, 0, 0, 0, 0, 0, 0, 0, PublicKey(0), 0, 0
        )

    async def get_unrealised_pnl(self, market_index=None):
        positions = await self.get_user_positions_account()

        pnl = 0
        for position in positions:
            if market_index is not None and position.market_index == market_index:
                market = self.clearing_house.get_market(
                    position.market_index
                )  # todo repeat querying
                pnl += calculate_position_pnl(market, position)

        return pnl

    async def get_total_collateral(self):
        collateral = await self.clearing_house.get_user_account().collatearl
        return collateral + self.get_unrealised_pnl()

    async def get_total_position_value(self):
        positions = await self.get_user_positions_account()
        value = 0
        for position in positions:
            market = self.clearing_house.get_market(
                position.market_index
            )  # todo repeat querying
            value += calculate_base_asset_value(market, position)

        return value

    async def get_position_value(self, market_index=None):
        positions = await self.get_user_positions_account()
        value = 0
        for position in positions:
            if market_index is not None and position.market_index == market_index:
                market = self.clearing_house.get_market(
                    position.market_index
                )  # todo repeat querying
                value += calculate_base_asset_value(market, position)
        return value
