# from turtle import pos
from driftpy.clearing_house import ClearingHouse
from solana.publickey import PublicKey
from typing import cast, Optional

from driftpy.constants.numeric_constants import *
from driftpy.types import *
from driftpy.accounts import *
from driftpy.math.positions import is_available, is_spot_position_available

from pythclient.pythaccounts import PythPriceAccount
from pythclient.solana import (
    SolanaClient,
    SolanaPublicKey,
    SOLANA_DEVNET_HTTP_ENDPOINT,
    SOLANA_DEVNET_WS_ENDPOINT,
    SOLANA_MAINNET_HTTP_ENDPOINT,
    SOLANA_MAINNET_WS_ENDPOINT,
)


def find(l: list, f):
    valid_values = [v for v in l if f(v)]
    if len(valid_values) == 0:
        return None
    else:
        return valid_values[0]


def convert_pyth_price(price):
    return int(price * PRICE_PRECISION)


@dataclass
class OracleData:
    price: int
    slot: int
    confidence: int
    twap: int
    twap_confidence: int
    has_sufficient_number_of_datapoints: bool


from solana.rpc.async_api import AsyncClient

# todo: support other than devnet
async def get_oracle_data(connection: AsyncClient, address: PublicKey) -> OracleData:
    address = str(address)
    account_key = SolanaPublicKey(address)

    http_endpoint = connection._provider.endpoint_uri
    ws_endpoint = http_endpoint.replace('https', 'wss')

    solana_client = SolanaClient(endpoint=http_endpoint, ws_endpoint=ws_endpoint)
    price: PythPriceAccount = PythPriceAccount(account_key, solana_client)
    await price.update()

    # TODO: returns none rn
    # (twap, twac) = (price.derivations.get('TWAPVALUE'), price.derivations.get('TWACVALUE'))
    (twap, twac) = (0, 0)

    oracle_data = OracleData(
        price=convert_pyth_price(price.aggregate_price_info.price),
        slot=price.last_slot,
        confidence=convert_pyth_price(price.aggregate_price_info.confidence_interval),
        twap=convert_pyth_price(twap),
        twap_confidence=convert_pyth_price(twac),
        has_sufficient_number_of_datapoints=True,
    )

    await solana_client.close()

    return oracle_data


def get_signed_token_amount(amount, balance_type):
    if (
        str(balance_type) == "SpotBalanceType.Deposit()"
    ):  # todo not sure how else to do comparisons
        return amount
    else:
        return -abs(amount)


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


def calculate_size_discount_asset_weight(
    size,
    imf_factor,
    asset_weight,
):
    if imf_factor == 0:
        return 0

    size_sqrt = int((size * 10) ** 0.5) + 1
    imf_num = SPOT_IMF_PRECISION + (SPOT_IMF_PRECISION / 10)

    size_discount_asset_weight = (
        imf_num
        * SPOT_WEIGHT_PRECISION
        / (SPOT_IMF_PRECISION + size_sqrt * imf_factor / 100_000)
    )

    min_asset_weight = min(asset_weight, size_discount_asset_weight)
    return min_asset_weight


from enum import Enum


class MarginCategory(Enum):
    INITIAL = "Initial"
    MAINTENANCE = "Maintenance"


def calculate_asset_weight(
    amount,
    spot_market: SpotMarket,
    margin_category: MarginCategory,
):
    size_precision = 10 ** spot_market.decimals

    if size_precision > AMM_RESERVE_PRECISION:
        size_in_amm_precision = amount / (size_precision / AMM_RESERVE_PRECISION)
    else:
        size_in_amm_precision = amount * AMM_RESERVE_PRECISION / size_precision

    match margin_category:
        case MarginCategory.INITIAL:
            asset_weight = calculate_size_discount_asset_weight(
                size_in_amm_precision,
                spot_market.imf_factor,
                spot_market.initial_asset_weight,
            )
        case MarginCategory.MAINTENANCE:
            asset_weight = calculate_size_discount_asset_weight(
                size_in_amm_precision,
                spot_market.imf_factor,
                spot_market.maintenance_asset_weight,
            )
        case None:
            asset_weight = spot_market.initial_asset_weight
        case _:
            raise Exception(f"Invalid margin category: {margin_category}")

    return asset_weight


def get_spot_asset_value(
    amount: int, oracle_data, spot_market: SpotMarket, margin_category: MarginCategory
):
    asset_value = get_token_value(amount, spot_market.decimals, oracle_data)

    if margin_category is not None:
        weight = calculate_asset_weight(amount, spot_market, margin_category)
        asset_value = asset_value * weight / SPOT_WEIGHT_PRECISION

    return asset_value


def get_worst_case_token_amounts(
    position: SpotPosition,
    spot_market: SpotMarket,
    oracle_data,
):

    token_amount = get_signed_token_amount(
        get_token_amount(position.scaled_balance, spot_market, position.balance_type),
        position.balance_type,
    )

    token_all_bids = token_amount + position.open_bids
    token_all_asks = token_amount + position.open_asks

    if abs(token_all_asks) > abs(token_all_bids):
        value = get_token_value(-position.open_asks, spot_market.decimals, oracle_data)
        return [token_all_asks, value]
    else:
        value = get_token_value(-position.open_bids, spot_market.decimals, oracle_data)
        return [token_all_bids, value]


def calculate_base_asset_value_with_oracle(
    perp_position: PerpPosition, oracle_data: OracleData
):
    return (
        abs(perp_position.base_asset_amount)
        * oracle_data.price
        * QUOTE_PRECISION
        / AMM_RESERVE_PRECISION
        / PRICE_PRECISION
    )


def calculate_position_funding_pnl(market: PerpMarket, perp_position: PerpPosition):
    if perp_position.base_asset_amount == 0:
        return 0

    amm_cumm_funding_rate = (
        market.amm.cumulative_funding_rate_long
        if perp_position.base_asset_amount > 0
        else market.amm.cumulative_funding_rate_short
    )

    funding_rate_pnl = (
        (amm_cumm_funding_rate - perp_position.last_cumulative_funding_rate)
        * perp_position.base_asset_amount
        / AMM_RESERVE_PRECISION
        / FUNDING_RATE_BUFFER
        * -1
    )

    return funding_rate_pnl


def calculate_position_pnl(
    market: PerpMarket,
    perp_position: PerpPosition,
    oracle_data,
    with_funding=False,
):
    if perp_position.base_asset_amount == 0:
        return perp_position.quote_asset_amount

    base_value = calculate_base_asset_value_with_oracle(perp_position, oracle_data)
    base_asset_sign = -1 if perp_position.base_asset_amount < 0 else 1
    pnl = base_value * base_asset_sign + perp_position.quote_asset_amount

    if with_funding:
        funding_pnl = calculate_position_funding_pnl(market, perp_position)
        pnl += funding_pnl

    return pnl


def calculate_worst_case_base_asset_amount(perp_position: PerpPosition):
    all_bids = perp_position.base_asset_amount + perp_position.open_bids
    all_asks = perp_position.base_asset_amount + perp_position.open_asks
    if abs(all_bids) > abs(all_asks):
        return all_bids
    else:
        return all_asks


def calculate_size_premium_liability_weight(
    size: int, imf_factor: int, liability_weight: int, precision: int
) -> int:
    if imf_factor == 0:
        return liability_weight

    size_sqrt = int((size * 10 + 1) ** 0.5)
    denom0 = max(1, SPOT_IMF_PRECISION / imf_factor)
    assert denom0 > 0
    liability_weight_numerator = liability_weight - (liability_weight / denom0)

    denom = 100_000 * SPOT_IMF_PRECISION / precision
    assert denom > 0

    size_premium_liability_weight = liability_weight_numerator + (
        size_sqrt * imf_factor / denom
    )
    max_liability_weight = max(liability_weight, size_premium_liability_weight)
    return max_liability_weight


def calculcate_liability_weight(
    balance_amount: int, spot_market: SpotMarket, margin_category: MarginCategory
) -> int:
    size_precision = 10 ** spot_market.decimals
    if size_precision > AMM_RESERVE_PRECISION:
        size_in_amm_reserve_precision = balance_amount / (
            size_precision / AMM_RESERVE_PRECISION
        )
    else:
        size_in_amm_reserve_precision = (
            balance_amount * AMM_RESERVE_PRECISION / size_precision
        )

    match margin_category:
        case MarginCategory.INITIAL:
            asset_weight = calculate_size_premium_liability_weight(
                size_in_amm_reserve_precision,
                spot_market.imf_factorm,
                spot_market.initial_liability_weight,
                SPOT_WEIGHT_PRECISION,
            )
        case MarginCategory.MAINTENANCE:
            asset_weight = calculate_size_premium_liability_weight(
                size_in_amm_reserve_precision,
                spot_market.imf_factorm,
                spot_market.maintenance_liability_weight,
                SPOT_WEIGHT_PRECISION,
            )
        case _:
            asset_weight = spot_market.initial_liability_weight

    return asset_weight


def calculate_market_margin_ratio(
    market: PerpMarket, size: int, margin_category: MarginCategory
) -> int:
    match margin_category:
        case MarginCategory.INITIAL:
            margin_ratio = calculate_size_premium_liability_weight(
                size, market.imf_factor, market.margin_ratio_initial, MARGIN_PRECISION
            )
        case MarginCategory.MAINTENANCE:
            margin_ratio = calculate_size_premium_liability_weight(
                size,
                market.imf_factor,
                market.margin_ratio_maintenance,
                MARGIN_PRECISION,
            )
    return margin_ratio


def get_spot_liability_value(
    token_amount: int,
    oracle_data: OracleData,
    spot_market: SpotMarket,
    margin_category: MarginCategory,
    liquidation_buffer: int = None,
    max_margin_ratio: int = None,
) -> int:
    liability_value = get_token_value(token_amount, spot_market.decimals, oracle_data)

    if margin_category is not None:
        weight = calculcate_liability_weight(token_amount, spot_market, margin_category)

        if margin_category == MarginCategory.INITIAL:
            assert max_margin_ratio, "set = user.max_margin_ratio"
            weight = max(weight, max_margin_ratio)

        if liquidation_buffer is not None:
            weight += liquidation_buffer

        liability_value = liability_value * weight / SPOT_WEIGHT_PRECISION

    return liability_value


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

    async def get_spot_market_liability(
        self,
        market_index=None,
        margin_category=None,
        liquidation_buffer=None,
        include_open_orders=None,
    ):
        user = await self.get_user_account()
        total_liability = 0
        for position in user.spot_positions:
            if is_spot_position_available(position) or (
                market_index is not None and position.market_index != market_index
            ):
                continue

            spot_market = await get_spot_market_account(
                self.program, position.market_index
            )

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

            oracle_data = await get_oracle_data(spot_market.oracle)
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
                    worst_case_token_amount,
                    oracle_data,
                    spot_market,
                    margin_category,
                    liquidation_buffer,
                    user.max_margin_ratio,
                )
                total_liability += baa_value

            if worst_case_quote_amount > 0:
                weight = SPOT_WEIGHT_PRECISION
                if margin_category == MarginCategory.INITIAL:
                    weight = max(weight, user.max_margin_ratio)
                weighted_value = (
                    worst_case_quote_amount * weight / SPOT_WEIGHT_PRECISION
                )
                total_liability += weighted_value

        return total_liability

    async def get_total_perp_positon(
        self,
        margin_category: Optional[MarginCategory] = None,
        liquidation_buffer: Optional[int] = 0,
        include_open_orders: bool = False,
    ):
        user = await self.get_user_account()
        unrealized_pnl = 0
        for position in user.perp_positions:
            market = await get_perp_market_account(self.program, position.market_index)

            if position.lp_shares > 0:
                pass

            price = (await get_oracle_data(market.amm.oracle)).price
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

        user = await self.get_user_account()
        liquidation_buffer = None
        if user.being_liquidated:
            liquidation_buffer = (
                await get_state_account(self.program)
            ).liquidation_margin_buffer_ratio

        maintenance_req = await self.get_margin_requirement(
            MarginCategory.MAINTENANCE, liquidation_buffer
        )

        return total_collateral < maintenance_req

    async def get_margin_requirement(
        self, margin_category: MarginCategory, liquidation_buffer: Optional[int] = 0
    ) -> int:
        perp_liability = self.get_total_perp_positon(
            margin_category, liquidation_buffer, True
        )
        spot_liability = self.get_spot_market_liability(
            None, margin_category, liquidation_buffer, True
        )
        return await perp_liability + await spot_liability

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
        total_collatearl = spot_collateral + pnl
        return total_collatearl

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
        user = await get_user_account(self.program, self.authority)

        found = False
        for position in user.spot_positions:
            if position.market_index == market_index and not is_spot_position_available(position):
                found = True
                break

        if not found:
            return None

        return position

    async def get_user_position(
        self,
        market_index: int,
    ) -> Optional[PerpPosition]:
        user = await get_user_account(self.program, self.authority)

        found = False
        for position in user.perp_positions:
            if position.market_index == market_index and not is_available(position):
                found = True
                break

        if not found:
            return None

        # assert position.market_index == market_index, "no position in market"
        return position

    async def get_unrealized_pnl(
        self,
        with_funding: bool = False,
        market_index: int = None,
        with_weight_margin_category: Optional[MarginCategory] = None,
    ):
        # quote_spot_market = get_spot_market_account(self.program, QUOTE_SPOT_MARKET_INDEX)
        user = await get_user_account(self.clearing_house.program, self.authority)
        unrealized_pnl = 0
        position: PerpPosition
        for position in user.perp_positions:
            if market_index is not None and position.market_index != market_index:
                continue

            market = await get_perp_market_account(self.program, position.market_index)
            oracle_data = await get_oracle_data(self.program.provider.connection, market.amm.oracle)
            position_unrealized_pnl = calculate_position_pnl(
                market, position, oracle_data, with_funding
            )

            if with_weight_margin_category is not None:
                raise NotImplementedError(
                    "Only with_weight_margin_category = None supported"
                )

            unrealized_pnl += position_unrealized_pnl

        return unrealized_pnl

    async def get_spot_market_asset_value(
        self,
        margin_category: Optional[MarginCategory] = None,
        include_open_orders=True,
        market_index: Optional[int] = None,
    ):
        user = await get_user_account(self.clearing_house.program, self.authority)
        total_value = 0
        for position in user.spot_positions:
            if is_spot_position_available(position) or (
                market_index is not None and position.market_index != market_index
            ):
                continue

            spot_market = await get_spot_market_account(
                self.program, position.market_index
            )

            if position.market_index == QUOTE_ASSET_BANK_INDEX:
                spot_token_value = get_token_amount(
                    position.scaled_balance, spot_market, position.balance_type
                )
                total_value += spot_token_value
                continue

            oracle_data = await get_oracle_data(spot_market.oracle)

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

    async def get_user_account(self) -> User:
        return await get_user_account(self.program, self.authority)

    async def get_leverage(
        self, margin_category: Optional[MarginCategory] = None
    ) -> int:
        total_liability = await self.get_margin_requirement(margin_category, None)
        total_asset_value = await self.get_total_collateral(margin_category)

        if total_asset_value == 0 or total_liability == 0:
            return 0

        leverage = total_liability * 10_000 / total_asset_value

        return leverage
