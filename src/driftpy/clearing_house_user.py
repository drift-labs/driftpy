from solana.publickey import PublicKey
from typing import Optional

from driftpy.clearing_house import ClearingHouse
from driftpy.constants.numeric_constants import *
from driftpy.types import *
from driftpy.accounts import *
from driftpy.math.positions import *
from driftpy.math.margin import *
from driftpy.math.spot_market import *
from driftpy.math.oracle import *

def find(l: list, f):
    valid_values = [v for v in l if f(v)]
    if len(valid_values) == 0:
        return None
    else:
        return valid_values[0]


class ClearingHouseUser:
    """This class is the main way to retrieve and inspect data on Drift Protocol.  
    """

    def __init__(
        self,
        clearing_house: ClearingHouse,
        authority: Optional[PublicKey] = None,
        subaccount_id: int = 0,
        use_cache: bool = False,
    ):
        """Initialize the clearing house user object

        Args:
            clearing_house (ClearingHouse): required for program_id, idl, things (keypair doesnt matter)
            authority (Optional[PublicKey], optional): authority to investigate if None will use clearing_house.authority
            subaccount_id (int, optional): subaccount of authority to investigate. Defaults to 0.
            use_cache (bool, optional): sdk uses a lot of rpc calls rn - use this flag and .set_cache() to cache accounts and reduce rpc calls. Defaults to False.
        """
        self.clearing_house = clearing_house
        self.authority = authority
        if self.authority is None:
            self.authority = clearing_house.authority

        self.program = clearing_house.program
        self.oracle_program = clearing_house
        self.connection = self.program.provider.connection
        self.subaccount_id = subaccount_id
        self.use_cache = use_cache
        self.cache_is_set = False

    # cache all state, perpmarket, oracle, etc. in single cache -- user calls reload 
    # when they want to update the data? 
        # get_spot_market
        # get_perp_market 
        # get_user 
        # if state = cache => get cached_market else get new market 
    async def set_cache_last(self, CACHE=None):
        """sets the cache of the accounts to use to inspect

        Args:
            CACHE (dict, optional): other existing cache object - if None will pull ƒresh accounts from RPC. Defaults to None.
        """
        self.cache_is_set = True

        if CACHE is not None:
            self.CACHE = CACHE
            return

        self.CACHE = {}
        state = await get_state_account(self.program)
        self.CACHE['state'] = state

        spot_markets = []
        spot_market_oracle_data = []
        for i in range(state.number_of_spot_markets):
            spot_market = await get_spot_market_account(
                self.program, i
            )
            spot_markets.append(spot_market)

            if i == 0: 
                spot_market_oracle_data.append(OracleData(
                    PRICE_PRECISION, 0, 1, 1, 0, True
                ))
            else:
                oracle_data = OracleData(
                    spot_market.historical_oracle_data.last_oracle_price, 0, 1, 1, 0, True
                )
                spot_market_oracle_data.append(oracle_data)
            
        self.CACHE['spot_markets'] = spot_markets
        self.CACHE['spot_market_oracles'] = spot_market_oracle_data
        
        perp_markets = []
        perp_market_oracle_data = []
        for i in range(state.number_of_markets):
            perp_market = await get_perp_market_account(
                self.program, i
            )
            perp_markets.append(perp_market)

            oracle_data = OracleData(
                    perp_market.amm.historical_oracle_data.last_oracle_price, 0, 1, 1, 0, True
                )
            perp_market_oracle_data.append(oracle_data)

        self.CACHE['perp_markets'] = perp_markets
        self.CACHE['perp_market_oracles'] = perp_market_oracle_data

        user = await get_user_account(
            self.program, self.authority, self.subaccount_id
        )
        self.CACHE['user'] = user

    async def set_cache(self, CACHE=None):
        """sets the cache of the accounts to use to inspect

        Args:
            CACHE (dict, optional): other existing cache object - if None will pull ƒresh accounts from RPC. Defaults to None.
        """
        self.cache_is_set = True

        if CACHE is not None:
            self.CACHE = CACHE
            return

        self.CACHE = {}
        state = await get_state_account(self.program)
        self.CACHE['state'] = state

        spot_markets = []
        spot_market_oracle_data = []
        for i in range(state.number_of_spot_markets):
            spot_market = await get_spot_market_account(
                self.program, i
            )
            spot_markets.append(spot_market)

            if i == 0: 
                spot_market_oracle_data.append(OracleData(
                    PRICE_PRECISION, 0, 1, 1, 0, True
                ))
            else:
                oracle_data = await get_oracle_data(self.connection, spot_market.oracle)
                spot_market_oracle_data.append(oracle_data)
            
        self.CACHE['spot_markets'] = spot_markets
        self.CACHE['spot_market_oracles'] = spot_market_oracle_data
        
        perp_markets = []
        perp_market_oracle_data = []
        for i in range(state.number_of_markets):
            perp_market = await get_perp_market_account(
                self.program, i
            )
            perp_markets.append(perp_market)

            oracle_data = await get_oracle_data(self.connection, perp_market.amm.oracle)
            perp_market_oracle_data.append(oracle_data)

        self.CACHE['perp_markets'] = perp_markets
        self.CACHE['perp_market_oracles'] = perp_market_oracle_data

        user = await get_user_account(
            self.program, self.authority, self.subaccount_id
        )
        self.CACHE['user'] = user

    async def get_spot_oracle_data(self, spot_market: SpotMarket):
        if self.use_cache: 
            assert self.cache_is_set, 'must call clearing_house_user.set_cache() first'
            return self.CACHE['spot_market_oracles'][spot_market.market_index]
        else: 
            oracle_data = await get_oracle_data(self.connection, spot_market.oracle)        
            return oracle_data
    
    async def get_perp_oracle_data(self, perp_market: PerpMarket):
        if self.use_cache: 
            assert self.cache_is_set, 'must call clearing_house_user.set_cache() first'
            return self.CACHE['perp_market_oracles'][perp_market.market_index]
        else: 
            oracle_data = await get_oracle_data(self.connection, perp_market.amm.oracle)        
            return oracle_data
    
    async def get_state(self):
        if self.use_cache: 
            assert self.cache_is_set, 'must call clearing_house_user.set_cache() first'
            return self.CACHE['state']
        else: 
            return await get_state_account(self.program)

    async def get_spot_market(self, i):
        if self.use_cache: 
            assert self.cache_is_set, 'must call clearing_house_user.set_cache() first'
            return self.CACHE['spot_markets'][i]
        else: 
            return await get_spot_market_account(
                self.program, i
            )
    
    async def get_perp_market(self, i):
        if self.use_cache: 
            assert self.cache_is_set, 'must call clearing_house_user.set_cache() first'
            return self.CACHE['perp_markets'][i]
        else: 
            return await get_perp_market_account(
                self.program, i
            )

    async def get_user(self):
        if self.use_cache: 
            assert self.cache_is_set, 'must call clearing_house_user.set_cache() first'
            return self.CACHE['user']
        else: 
            return await get_user_account(
                self.program, self.authority, self.subaccount_id
            )

    async def get_spot_market_liability(
        self,
        market_index=None,
        margin_category=None,
        liquidation_buffer=None,
        include_open_orders=None,
    ):
        user = await self.get_user()
        total_liability = 0
        for position in user.spot_positions:
            if is_spot_position_available(position) or (
                market_index is not None and position.market_index != market_index
            ):
                continue

            spot_market = await self.get_spot_market(position.market_index)

            if position.market_index == QUOTE_ASSET_BANK_INDEX:
                if str(position.balance_type) == "SpotBalanceType.Borrow()":
                    token_amount = get_token_amount(
                        position.scaled_balance, spot_market, position.balance_type
                    )
                    weight = SPOT_WEIGHT_PRECISION
                    if margin_category == MarginCategory.INITIAL:
                        weight = max(weight, user.max_margin_ratio)

                    value = token_amount * weight / SPOT_WEIGHT_PRECISION
                    total_liability += value
                    continue
                else:
                    continue

            oracle_data = await self.get_spot_oracle_data(spot_market)
            if not include_open_orders:
                if str(position.balance_type) == "SpotBalanceType.Borrow()":
                    token_amount = get_token_amount(
                        position.scaled_balance, spot_market, position.balance_type
                    )
                    liability_value = get_spot_liability_value(
                        token_amount,
                        oracle_data,
                        spot_market,
                        margin_category,
                        liquidation_buffer,
                        user.max_margin_ratio,
                    )
                    total_liability += liability_value
                    continue
                else:
                    continue

            (
                worst_case_token_amount,
                worst_case_quote_amount,
            ) = get_worst_case_token_amounts(position, spot_market, oracle_data)

            if worst_case_token_amount < 0:
                baa_value = get_spot_liability_value(
                    abs(worst_case_token_amount),
                    oracle_data,
                    spot_market,
                    margin_category,
                    liquidation_buffer,
                    user.max_margin_ratio,
                )
                total_liability += baa_value

            if worst_case_quote_amount < 0:
                weight = SPOT_WEIGHT_PRECISION
                if margin_category == MarginCategory.INITIAL:
                    weight = max(weight, user.max_margin_ratio)
                weighted_value = (
                    abs(worst_case_quote_amount) * weight / SPOT_WEIGHT_PRECISION
                )
                total_liability += weighted_value

        return total_liability

    async def get_total_perp_liability(
        self,
        margin_category: Optional[MarginCategory] = None,
        liquidation_buffer: Optional[int] = 0,
        include_open_orders: bool = False,
    ):
        user = await self.get_user()

        unrealized_pnl = 0
        for position in user.perp_positions:
            market = await self.get_perp_market(position.market_index)

            if position.lp_shares > 0:
                pass

            price = (await self.get_perp_oracle_data(market)).price
            base_asset_amount = (
                calculate_worst_case_base_asset_amount(position)
                if include_open_orders
                else position.base_asset_amount
            )
            base_value = (
                abs(base_asset_amount)
                * price
                / (AMM_TO_QUOTE_PRECISION_RATIO * PRICE_PRECISION)
            )

            if margin_category is not None:
                margin_ratio = calculate_market_margin_ratio(
                    market, abs(base_asset_amount), margin_category
                )

                if margin_category == MarginCategory.INITIAL:
                    margin_ratio = max(margin_ratio, user.max_margin_ratio)

                if liquidation_buffer is not None:
                    margin_ratio += liquidation_buffer

                base_value = base_value * margin_ratio / MARGIN_PRECISION

            unrealized_pnl += base_value
        return unrealized_pnl

    async def can_be_liquidated(self) -> bool:
        total_collateral = await self.get_total_collateral()

        user = await self.get_user()
        liquidation_buffer = None
        if user.being_liquidated:
            liquidation_buffer = (
                await self.get_state()
            ).liquidation_margin_buffer_ratio

        maintenance_req = await self.get_margin_requirement(
            MarginCategory.MAINTENANCE, liquidation_buffer
        )

        return total_collateral < maintenance_req

    async def get_margin_requirement(
        self, margin_category: MarginCategory, liquidation_buffer: Optional[int] = 0,
        include_open_orders=True,
        include_spot=True
    ) -> int:
        perp_liability = await self.get_total_perp_liability(
            margin_category, liquidation_buffer, include_open_orders
        )
        
        result = perp_liability
        if include_spot:
            spot_liability = await self.get_spot_market_liability(
            None, margin_category, liquidation_buffer, include_open_orders
            )
            result += spot_liability

        return result

    async def get_total_collateral(
        self, margin_category: Optional[MarginCategory] = None
    ) -> int:
        spot_collateral = await self.get_spot_market_asset_value(
            margin_category,
            include_open_orders=True,
        )
        pnl = await self.get_unrealized_pnl(
            True, with_weight_margin_category=margin_category
        )
        total_collateral = spot_collateral + pnl
        return total_collateral

    async def get_free_collateral(self):
        total_collateral = await self.get_total_collateral()
        init_margin_req = await self.get_margin_requirement(
            MarginCategory.INITIAL,
        )
        free_collateral = total_collateral - init_margin_req
        free_collateral = max(0, free_collateral)
        return free_collateral

    async def get_user_spot_position(
        self,
        market_index: int,
    ) -> Optional[SpotPosition]:
        user = await self.get_user()

        found = False
        for position in user.spot_positions:
            if (
                position.market_index == market_index
                and not is_spot_position_available(position)
            ):
                found = True
                break

        if not found:
            return None

        return position

    async def get_user_position(
        self,
        market_index: int,
    ) -> Optional[PerpPosition]:
        user = await self.get_user()

        found = False
        for position in user.perp_positions:
            if position.market_index == market_index and not is_available(position):
                found = True
                break

        if not found:
            return None

        return position

    async def get_unrealized_pnl(
        self,
        with_funding: bool = False,
        market_index: int = None,
        with_weight_margin_category: Optional[MarginCategory] = None,
    ):
        user = await self.get_user()
        quote_spot_market = await self.get_spot_market(QUOTE_ASSET_BANK_INDEX)

        unrealized_pnl = 0
        position: PerpPosition
        for position in user.perp_positions:
            if market_index is not None and position.market_index != market_index:
                continue
            
            market = await self.get_perp_market(position.market_index)

            oracle_data = await self.get_perp_oracle_data(market)
            position_unrealized_pnl = calculate_position_pnl_with_oracle(
                market, position, oracle_data, with_funding
            )

            if with_weight_margin_category is not None:
                if position_unrealized_pnl > 0: 
                    unrealized_asset_weight = calculate_unrealized_asset_weight(
                        market, 
                        quote_spot_market, 
                        position_unrealized_pnl,
                        with_weight_margin_category, 
                        oracle_data
                    )
                    position_unrealized_pnl = position_unrealized_pnl * unrealized_asset_weight / SPOT_WEIGHT_PRECISION

            unrealized_pnl += position_unrealized_pnl

        return unrealized_pnl

    async def get_spot_market_asset_value(
        self,
        margin_category: Optional[MarginCategory] = None,
        include_open_orders=True,
        market_index: Optional[int] = None,
    ):
        user = await self.get_user()
        total_value = 0
        for position in user.spot_positions:
            if is_spot_position_available(position) or (
                market_index is not None and position.market_index != market_index
            ):
                continue

            spot_market = await self.get_spot_market(position.market_index)

            if position.market_index == QUOTE_ASSET_BANK_INDEX:
                spot_token_value = get_token_amount(
                    position.scaled_balance, spot_market, position.balance_type
                )

                match str(position.balance_type):
                    case "SpotBalanceType.Deposit()":
                        spot_token_value *= 1
                    case "SpotBalanceType.Borrow()":
                        spot_token_value *= -1
                    case _:
                        raise Exception(f"Invalid balance type: {position.balance_type}")

                total_value += spot_token_value
                continue

            oracle_data = await self.get_spot_oracle_data(spot_market)

            if not include_open_orders:
                if str(position.balance_type) == "SpotBalanceType.Deposit()":
                    token_amount = get_token_amount(
                        position.scaled_balance, spot_market, position.balance_type
                    )
                    asset_value = get_spot_asset_value(
                        token_amount, oracle_data, spot_market, margin_category
                    )
                    total_value += asset_value
                    continue
                else:
                    continue

            (
                worst_case_token_amount,
                worst_case_quote_amount,
            ) = get_worst_case_token_amounts(position, spot_market, oracle_data)

            if worst_case_token_amount > 0:
                baa_value = get_spot_asset_value(
                    worst_case_token_amount, oracle_data, spot_market, margin_category
                )
                total_value += baa_value

            if worst_case_quote_amount > 0:
                total_value += worst_case_quote_amount

        return total_value

    async def get_leverage(
        self, margin_category: Optional[MarginCategory] = None
    ) -> int:
        total_liability = await self.get_margin_requirement(margin_category, None)
        total_asset_value = await self.get_total_collateral(margin_category)

        if total_asset_value == 0 or total_liability == 0:
            return 0

        leverage = total_liability * 10_000 / total_asset_value

        return leverage

    async def get_perp_liq_price(
        self, 
        perp_market_index: int, 
    ) -> Optional[int]:
        position = await self.get_user_position(perp_market_index)
        if position is None or position.base_asset_amount == 0:
            return None

        total_collateral = await self.get_total_collateral(MarginCategory.MAINTENANCE)
        margin_req = await self.get_margin_requirement(MarginCategory.MAINTENANCE)
        delta_liq = total_collateral - margin_req

        perp_market = await self.get_perp_market(perp_market_index)
        delta_per_baa = delta_liq / (position.base_asset_amount / AMM_RESERVE_PRECISION)
        
        oracle_price = (await self.get_perp_oracle_data(perp_market)).price / PRICE_PRECISION

        liq_price = oracle_price - (delta_per_baa / QUOTE_PRECISION)
        if liq_price < 0:
            return None

        return liq_price

    async def get_spot_liq_price(
        self, 
        spot_market_index: int, 
    ) -> Optional[int]:
        position = await self.get_user_spot_position(spot_market_index)
        if position is None: 
            return None

        total_collateral = await self.get_total_collateral(MarginCategory.MAINTENANCE)
        margin_req = await self.get_margin_requirement(MarginCategory.MAINTENANCE, None, True, False)
        delta_liq = total_collateral - margin_req

        spot_market = await self.get_spot_market(spot_market_index)
        token_amount = get_token_amount(
            position.scaled_balance, 
            spot_market, 
            position.balance_type
        )
        token_amount_qp = token_amount * QUOTE_PRECISION / (10 ** spot_market.decimals)
        if abs(token_amount_qp) == 0: 
            return None 

        match str(position.balance_type):
            case "SpotBalanceType.Borrow()":
                liq_price_delta = (
                    delta_liq 
                    * PRICE_PRECISION
                    * SPOT_WEIGHT_PRECISION
                    / token_amount_qp
                    / spot_market.maintenance_liability_weight
                )
            case "SpotBalanceType.Deposit()":
                liq_price_delta = (
                    delta_liq 
                    * PRICE_PRECISION
                    * SPOT_WEIGHT_PRECISION
                    / token_amount_qp
                    / spot_market.maintenance_asset_weight
                    * -1 
                )
            case _:
                raise Exception(f"Invalid balance type: {position.balance_type}")
        
        price = (await self.get_spot_oracle_data(spot_market)).price
        liq_price = price + liq_price_delta
        liq_price /= PRICE_PRECISION

        if liq_price < 0:
            return None
        
        return liq_price
