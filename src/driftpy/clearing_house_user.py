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

from driftpy.constants.numeric_constants import *
from driftpy.types import *
from driftpy.accounts import *

from pythclient.pythaccounts import PythPriceAccount
from pythclient.solana import (SolanaClient, SolanaPublicKey, SOLANA_DEVNET_HTTP_ENDPOINT, SOLANA_DEVNET_WS_ENDPOINT,
    SOLANA_MAINNET_HTTP_ENDPOINT, SOLANA_MAINNET_HTTP_ENDPOINT)

def find(l: list, f):
    valid_values = [v for v in l if f(v)]
    if len(valid_values) == 0:
        return None
    else: 
        return valid_values[0]

async def convert_pyth_price(price):
    return int(price * PRICE_PERCISION)

# todo: support other than devnet
async def get_oracle_data(address: str):
    account_key = SolanaPublicKey(address)
    solana_client = SolanaClient(endpoint=SOLANA_DEVNET_HTTP_ENDPOINT, ws_endpoint=SOLANA_DEVNET_WS_ENDPOINT)
    price: PythPriceAccount = PythPriceAccount(account_key, solana_client)
    await price.update()

    (twap, twac) = (price.derivations.get('TWAPVALUE'), price.derivations.get('TWACVALUE'))

    return dict( 
        price = convert_pyth_price(price.aggregate_price),
        slot = price.last_slot, 
        confidence = convert_pyth_price(price.aggregate_price_confidence_interval),
        twap = convert_pyth_price(twap),
        twap_confidence = convert_pyth_price(twac),
        has_sufficient_number_of_datapoints = True
    )

def get_signed_token_amount(
    amount, 
    balance_type
):
    if str(balance_type) == 'SpotBalanceType.Deposit()': # todo not sure how else to do comparisons
        return amount
    else: 
        return -abs(amount)

def get_token_amount(
    balance: int, 
    spot_market: SpotMarket,
    balance_type: SpotBalanceType
) -> int: 
    percision_decrease = 10 ** (16 - spot_market.decimals)

    match str(balance_type):
        case 'SpotBalanceType.Deposit()':
            cumm_interest = spot_market.cumulative_deposit_interest
        case 'SpotBalanceType.Borrow()':
            cumm_interest = spot_market.cumulative_borrow_interest
        case _: 
            raise Exception(f"Invalid balance type: {balance_type}")

    return balance * cumm_interest / percision_decrease

def is_spot_position_available(
    position: SpotPosition
):
    return position.balance == 0 and position.open_orders == 0

def get_token_value(
    amount, 
    spot_decimals, 
    oracle_data
):
    precision_decrease = 10 ** spot_decimals
    return amount * oracle_data['price'] / precision_decrease

def calculate_size_discount_asset_weight(
    size, 
    imf_factor, 
    asset_weight,
):
    if imf_factor == 0: 
        return 0 
    
    size_sqrt = int((size * 10) ** .5) + 1
    imf_num = SPOT_MARKET_IMF_PRECISION + (SPOT_MARKET_IMF_PRECISION / 10)

    size_discount_asset_weight = imf_num * SPOT_MARKET_WEIGHT_PRECISION / ( 
        SPOT_MARKET_IMF_PRECISION + size_sqrt * imf_factor / 100_000
    )

    min_asset_weight = min(asset_weight, size_discount_asset_weight)
    return min_asset_weight

def calculate_asset_weight(
    amount, 
    spot_market: SpotMarket, 
    margin_category,
):
    size_precision = 10 ** spot_market.decimals

    if size_precision > AMM_RESERVE_PRECISION:
        size_in_amm_precision = amount / (size_precision / AMM_RESERVE_PRECISION)
    else: 
        size_in_amm_precision = amount * AMM_RESERVE_PRECISION / size_precision

    match margin_category:
        case 'Initial': 
            asset_weight = calculate_size_discount_asset_weight(
                size_in_amm_precision, 
                spot_market.imf_factor, 
                spot_market.initial_asset_weight
            )
        case 'Maintenance':
            asset_weight = calculate_size_discount_asset_weight(
                size_in_amm_precision, 
                spot_market.imf_factor, 
                spot_market.maintenance_asset_weight
            )
        case None: 
            asset_weight = spot_market.initial_asset_weight
        case _: 
            raise Exception(f"Invalid margin category: {margin_category}")
    
    return asset_weight

def get_spot_asset_value(
    amount: int, 
    oracle_data, 
    spot_market: SpotMarket,
    margin_category
):
    asset_value = get_token_value(
        amount, 
        spot_market.decimals,
        oracle_data
    )

    if margin_category is not None: 
        weight = calculate_asset_weight(
            amount, 
            spot_market, 
            margin_category
        )
        asset_value = asset_value * weight / SPOT_MARKET_WEIGHT_PRECISION

    return asset_value

def get_worst_case_token_amounts(
    position: SpotPosition, 
    spot_market: SpotMarket, 
    oracle_data, 
): 

    token_amount = get_signed_token_amount(
        get_token_amount(
            position.balance, 
            spot_market, 
            position.balance_type
        ),
        position.balance_type,
    )

    token_all_bids = token_amount + position.open_bids
    token_all_asks = token_amount + position.open_asks

    if abs(token_all_asks) > abs(token_all_bids):
        value = get_token_value(
            -position.open_asks,
            spot_market.decimals,
            oracle_data
        )
        return [token_all_asks, value]
    else:
        value = get_token_value(
            -position.open_bids,
            spot_market.decimals,
            oracle_data
        )
        return [token_all_bids, value]


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
        if self.authority is None: 
            self.authority = clearing_house.authority

        self.program = clearing_house.program
        self.oracle_program = clearing_house

    async def get_spot_market_asset_value(
        self, 
        margin_category,
        include_open_orders
    ):
        user = await get_user_account(self.clearing_house.program, self.authority)
        total_value = 0 
        for position in user.spot_positions:
            if is_spot_position_available(position): 
                continue
            
            spot_market = await get_spot_market_account(
                self.program, 
                position.market_index
            )

            if position.market_index == QUOTE_ASSET_BANK_INDEX:
                total_value += get_token_amount(
                    position.balance, 
                    spot_market, 
                    position.balance_type
                )
                continue
            
            oracle_data = await get_oracle_data(spot_market.oracle)

            if not include_open_orders:
                if str(position.balance_type) == 'SpotBalanceType.Deposit()':
                    token_amount = get_token_amount(
                        position.balance, 
                        spot_market, 
                        position.balance_type
                    )
                    asset_value = get_spot_asset_value(
                        token_amount, 
                        oracle_data, 
                        spot_market,
                        margin_category
                    )
                    total_value += asset_value
                    continue
                else: 
                    continue
            
            worst_case_token_amount, worst_case_quote_amount = get_worst_case_token_amounts(
                position, 
                spot_market, 
                oracle_data
            )

            if worst_case_token_amount > 0:
                baa_value = get_spot_asset_value(
                    worst_case_token_amount, 
                    oracle_data, 
                    spot_market, 
                    margin_category
                )
                total_value += baa_value
            
            if worst_case_quote_amount > 0:
                total_value += worst_case_quote_amount

        return total_value
    
    async def get_user_account(self) -> User:
        return await get_user_account(
            self.program, 
            self.authority
        )

    async def get_user_position(self, market_index: int) -> PerpPosition:
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
