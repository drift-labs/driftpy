# from turtle import pos
from driftpy.clearing_house import ClearingHouse
from solana.publickey import PublicKey
from typing import cast, Optional
from driftpy.math.market import calculate_mark_price

from driftpy.setup.helpers import get_feed_data
from driftpy.math.positions import (
    calculate_base_asset_value,
    calculate_position_pnl,
)

from driftpy.constants.numeric_constants import (
    AMM_RESERVE_PRECISION,
)

import driftpy
from driftpy.constants.numeric_constants import QUOTE_ASSET_BANK_INDEX
from driftpy.types import (
    OracleSource,
    Order,
    MarketPosition,
    User,
)

from driftpy.accounts import (
    get_market_account, 
    get_spot_market_account,
    get_user_account
)

def find(l: list, f):
    valid_values = [v for v in l if f(v)]
    if len(valid_values) == 0:
        return None
    else: 
        return valid_values[0]

class ClearingHouseUser:
    """This class is the main way to interact with Drift Protocol.

    It allows you to subscribe to the various accounts where the Market's state is
    stored, as well as: opening positions, liquidating, settling funding, depositing &
    withdrawing, and more.

    The default way to construct a ClearingHouse instance is using the
    [create][driftpy.clearing_house.ClearingHouse.create] method.
    """

    def __init__(
        self,
        clearing_house: ClearingHouse,
        authority: Optional[PublicKey] = None,
    ):
        """Initialize the ClearingHouse object.

        Note: you probably want to use
        [create][driftpy.clearing_house.ClearingHouse.create]
        instead of this method.

        Args:
            clearing_house: The Drift ClearingHouse object.
            authority: user authority to focus on (if None, the clearing 
            house's .program.provider.wallet.pk is used as the auth)
        """
        self.clearing_house = clearing_house
        self.authority = authority
        self.program = clearing_house.program
        self.oracle_program = clearing_house
    
    async def get_user_account(self) -> User:
        return await get_user_account(
            self.program, 
            self.authority
        )

    async def get_user_position(self, market_index: int) -> MarketPosition:
        user = await self.get_user_account()

        position, found = find(user.positions, lambda p: p.market_index == market_index)
        if not found: 
            raise Exception("no position in market")
        
        return position

    async def get_user_order(self, order_id: int) -> Order:
        user = await self.get_user_account()

        order, found = find(user.orders, lambda o: o.order_id == order_id)
        if not found: 
            raise Exception("no order in market")
        return order

    async def get_unrealised_pnl(self, market_index: int = None):
        assert market_index is None or int(market_index) >= 0
        user = await self.get_user_account()

        from driftpy.setup.helpers import get_oracle_data

        pnl = 0
        for position in user.positions:
            if position.base_asset_amount != 0:
                if market_index is None or position.market_index == market_index:
                    market = await get_market_account(
                        self.program, 
                        position.market_index
                    )

                    assert market.amm.oracle_source == OracleSource.Pyth(), 'only pyth oracles supported rn'
                    oracle_data = await get_oracle_data(
                        self.program.provider.connection, 
                        market.amm.oracle,
                    )

                    market_pnl = calculate_position_pnl(market, position)
                    print(f'market {position.market_index} pnl {market_pnl}')
                    pnl += market_pnl

        return pnl

    async def get_collateral(self):
        collateral = (await self.clearing_house.get_user_account(
            self.authority
        )).collateral
        return collateral

    async def get_total_collateral(self):
        collateral = await self.get_collateral()
        return collateral + await self.get_unrealised_pnl()

    async def get_total_position_value(self):
        positions_account = await self.get_user_positions_account()
        value = 0
        for position in positions_account.positions:
            market = await self.clearing_house.get_market(
                position.market_index
            )  # todo repeat querying
            value += calculate_base_asset_value(market, position)

        return value

    async def get_position_value(self, market_index: int = None):
        assert market_index is None or int(market_index) >= 0
        positions_account = await self.get_user_positions_account()
        value = 0
        for position in positions_account.positions:
            if position.base_asset_amount != 0:
                if market_index is None or position.market_index == int(market_index):
                    market = await self.clearing_house.get_market(
                        position.market_index
                    )  # todo repeat querying
                    value += calculate_base_asset_value(market, position)
        return value

    async def get_margin_ratio(self):
        return await self.get_total_collateral() / await self.get_total_position_value()

    async def get_leverage(self):
        return (await self.get_total_position_value()) / (
            await self.get_total_collateral()
        )

    async def get_free_collateral(self):
        return (await self.get_total_collateral()) - (
            (await self.get_margin_requirement("initial"))
        )

    async def get_margin_requirement(self, kind):
        assert kind in ["initial", "partial", "maintenance"]

        positions_account = await self.get_user_positions_account()
        value = 0
        for position in positions_account.positions:
            if position.base_asset_amount != 0:
                market = await self.clearing_house.get_market(
                    position.market_index
                )  # todo repeat querying

                mr = None
                if kind == "partial":
                    mr = market.margin_ratio_partial
                elif kind == "initial":
                    mr = market.margin_ratio_initial
                else:
                    mr = market.margin_ratio_maintenance

                value += calculate_base_asset_value(market, position) * (mr / 10000)
        return value

    async def can_be_liquidated(self):
        return await self.get_total_collateral() <= await self.get_margin_requirement(
            "partial"
        )

    async def liquidation_price(self, market_index: int):
        # todo

        tc = await self.get_total_collateral()
        tpv = await self.get_total_position_value()
        free_collateral = (
            await self.get_free_collateral()
        )  # todo: use maint/partial lev
        partial_lev = 16
        # maint_lev = 20

        lev = partial_lev  # todo: param

        # this_level = partial_lev #if partial else maint_lev

        market = await self.clearing_house.get_market(market_index)

        position = await self.get_user_position(market_index)
        if position.base_asset_amount > 0 and tpv < free_collateral:
            return -1

        price_delt = None
        if position.base_asset_amount > 0:
            price_delt = tc * lev - tpv / (lev - 1)
        else:
            price_delt = tc * lev - tpv / (lev + 1)

        current_price = calculate_mark_price(market)

        eat_margin = price_delt * AMM_RESERVE_PRECISION / position.base_asset_amount
        if eat_margin > current_price:
            return -1

        liq_price = current_price - eat_margin

        return liq_price
