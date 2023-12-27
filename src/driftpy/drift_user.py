from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.math.amm import calculate_market_open_bid_ask
from driftpy.math.perp_position import *
from driftpy.math.margin import *
from driftpy.math.spot_market import *
from driftpy.accounts.oracle import *
from driftpy.math.spot_position import (
    get_worst_case_token_amounts,
    is_spot_position_available,
)
from driftpy.math.amm import calculate_market_open_bid_ask
from driftpy.types import OraclePriceData

from typing import Tuple
import copy


class DriftUser:
    """This class is the main way to retrieve and inspect drift user account data."""

    def __init__(
        self,
        drift_client,
        user_public_key: Pubkey,
        sub_account_id: int = 0,
        account_subscription: Optional[
            AccountSubscriptionConfig
        ] = AccountSubscriptionConfig.default(),
    ):
        """Initialize the user object

        Args:
            drift_client(DriftClient): required for program_id, idl, things (keypair doesnt matter)
            user_public_key (Pubkey): pubkey for user account
            sub_account_id (int, optional): subaccount of authority to investigate. Defaults to 0.
        """
        from driftpy.drift_client import DriftClient

        self.drift_client: DriftClient = drift_client
        self.program = drift_client.program
        self.oracle_program = drift_client
        self.connection = self.program.provider.connection
        self.subaccount_id = sub_account_id

        self.user_public_key = user_public_key

        self.account_subscriber = account_subscription.get_user_client_subscriber(
            self.program, self.user_public_key
        )

    async def subscribe(self):
        await self.account_subscriber.subscribe()

    def unsubscribe(self):
        self.account_subscriber.unsubscribe()

    def get_oracle_data_for_spot_market(
        self, market_index: int
    ) -> Optional[OraclePriceData]:
        return self.drift_client.get_oracle_price_data_for_spot_market(market_index)

    def get_oracle_data_for_perp_market(
        self, market_index: int
    ) -> Optional[OraclePriceData]:
        return self.drift_client.get_oracle_price_data_for_perp_market(market_index)

    def get_perp_market_account(self, market_index: int) -> PerpMarketAccount:
        return self.drift_client.get_perp_market_account(market_index)

    def get_spot_market_account(self, market_index: int) -> SpotMarketAccount:
        return self.drift_client.get_spot_market_account(market_index)

    def get_user_account_and_slot(self) -> DataAndSlot[UserAccount]:
        return self.account_subscriber.get_user_account_and_slot()

    def get_user_account(self) -> UserAccount:
        return self.account_subscriber.get_user_account_and_slot().data

    def get_token_amount(self, market_index: int) -> int:
        spot_position = self.get_spot_position(market_index)
        if spot_position is None:
            return 0

        spot_market = self.get_spot_market_account(market_index)
        token_amount = get_token_amount(
            spot_position.scaled_balance, spot_market, spot_position.balance_type
        )
        return get_signed_token_amount(token_amount, spot_position.balance_type)

    def get_order(self, order_id: int) -> Optional[Order]:
        for order in self.get_user_account().orders:
            if order.order_id == order_id:
                return order

        return None

    def get_order_by_user_order_id(self, user_order_id: int):
        for order in self.get_user_account().orders:
            if order.user_order_id == user_order_id:
                return order

        return None

    def get_open_orders(
        self,
    ):
        return list(
            filter(
                lambda order: "Open" in str(order.status),
                self.get_user_account().orders,
            )
        )

    def get_perp_position(self, market_index: int) -> Optional[PerpPosition]:
        for position in self.get_user_account().perp_positions:
            if position.market_index == market_index and not is_available(position):
                return position

        return None

    def get_spot_position(self, market_index: int) -> Optional[SpotPosition]:
        for position in self.get_user_account().spot_positions:
            if (
                position.market_index == market_index
                and not is_spot_position_available(position)
            ):
                return position

        return None

    def get_perp_market_liability(
        self,
        market_index: int = None,
        margin_category: Optional[MarginCategory] = None,
        liquidation_buffer: Optional[int] = 0,
        include_open_orders: bool = False,
        signed: bool = False,
    ):
        user = self.get_user_account()

        total_liability_value = 0
        for position in user.perp_positions:
            if market_index is not None and market_index != position.market_index:
                continue

            if position.lp_shares > 0:
                continue

            market = self.drift_client.get_perp_market_account(position.market_index)

            price = self.drift_client.get_oracle_price_data(market.amm.oracle).price
            base_asset_amount = (
                calculate_worst_case_base_asset_amount(position)
                if include_open_orders
                else position.base_asset_amount
            )
            base_value = (
                ((base_asset_amount) if signed else abs(base_asset_amount))
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

            total_liability_value += base_value
        return total_liability_value

    def can_be_liquidated(self) -> bool:
        total_collateral = self.get_total_collateral()

        user = self.get_user_account()
        liquidation_buffer = None
        if "BeingLiquidated" in user.status:
            liquidation_buffer = (
                self.drift_client.get_state_account()
            ).liquidation_margin_buffer_ratio

        maintenance_req = self.get_margin_requirement(
            MarginCategory.MAINTENANCE, liquidation_buffer
        )

        return total_collateral < maintenance_req

    def get_margin_requirement(
        self,
        margin_category: MarginCategory = MarginCategory.INITIAL,
        liquidation_buffer: Optional[int] = 0,
        include_spot=True,
    ) -> int:
        perp_liability = self.get_perp_market_liability(
            margin_category, liquidation_buffer, include_open_orders=True
        )

        result = perp_liability
        if include_spot:
            spot_liability = self.get_spot_market_liability(
                None,
                margin_category,
                liquidation_buffer,
                include_open_orders=True,
            )
            result += spot_liability

        return result

    def get_total_collateral(
        self, margin_category: Optional[MarginCategory] = MarginCategory.INITIAL
    ) -> int:
        asset_value = self.get_spot_market_asset_value(
            margin_category,
            include_open_orders=True,
        )
        pnl = self.get_unrealized_pnl(True, with_weight_margin_category=margin_category)
        total_collateral = asset_value + pnl
        return total_collateral

    def get_free_collateral(
        self, margin_category: MarginCategory = MarginCategory.INITIAL
    ):
        total_collateral = self.get_total_collateral(margin_category)
        init_margin_req = self.get_margin_requirement(margin_category)
        free_collateral = total_collateral - init_margin_req
        free_collateral = max(0, free_collateral)
        return free_collateral

    def get_user_spot_position(
        self,
        market_index: int,
    ) -> Optional[SpotPosition]:
        user = self.get_user_account()

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

    def get_user_position(
        self,
        market_index: int,
    ) -> Optional[PerpPosition]:
        user = self.get_user_account()

        found = False
        for position in user.perp_positions:
            if position.market_index == market_index and not is_available(position):
                found = True
                break

        if not found:
            return None

        return position

    def get_unrealized_pnl(
        self,
        with_funding: bool = False,
        market_index: int = None,
        with_weight_margin_category: Optional[MarginCategory] = None,
    ):
        user = self.get_user_account()
        quote_spot_market = self.drift_client.get_spot_market_account(
            QUOTE_SPOT_MARKET_INDEX
        )

        unrealized_pnl = 0
        for position in user.perp_positions:
            if market_index is not None and position.market_index != market_index:
                continue

            market = self.drift_client.get_perp_market_account(position.market_index)

            oracle_data = self.drift_client.get_oracle_price_data(market.amm.oracle)
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
                        oracle_data,
                    )
                    position_unrealized_pnl = (
                        position_unrealized_pnl
                        * unrealized_asset_weight
                        / SPOT_WEIGHT_PRECISION
                    )

            unrealized_pnl += position_unrealized_pnl

        return unrealized_pnl

    def get_unrealized_funding_pnl(
        self,
        market_index: int = None,
    ):
        user = self.get_user_account()

        unrealized_pnl = 0
        for position in user.perp_positions:
            if market_index is not None and position.market_index != market_index:
                continue

            perp_market = self.drift_client.get_perp_market_account(
                position.market_index
            )

            unrealized_pnl += calculate_position_funding_pnl(perp_market, position)

        return unrealized_pnl

    def get_spot_market_asset_and_liability_value(
        self,
        market_index: int = None,
        margin_category: MarginCategory = None,
        liquidation_buffer: int = None,
        include_open_orders: bool = True,
    ) -> (int, int):
        net_quote_value = 0
        total_asset_value = 0
        total_liability_value = 0
        for spot_position in self.get_user_account().spot_positions:
            count_for_base = (
                market_index is None or market_index == spot_position.market_index
            )
            count_for_quote = (
                market_index is None
                or market_index == QUOTE_SPOT_MARKET_INDEX
                or (include_open_orders and spot_position.open_orders != 0)
            )

            if is_spot_position_available(spot_position) or (
                not count_for_base and not count_for_quote
            ):
                continue

            spot_market_account = self.drift_client.get_spot_market_account(
                spot_position.market_index
            )

            oracle_price_data = self.drift_client.get_oracle_price_data(
                spot_market_account.oracle
            )

            if (
                spot_market_account.market_index == QUOTE_SPOT_MARKET_INDEX
                and count_for_quote
            ):
                token_amount = get_signed_token_amount(
                    get_token_amount(
                        spot_position.scaled_balance,
                        spot_market_account,
                        spot_position.balance_type,
                    ),
                    spot_position.balance_type,
                )

                if is_variant(spot_position.balance_type, "Borrow"):
                    weighted_token_value = abs(
                        self.get_spot_liability_value(
                            token_amount,
                            oracle_price_data,
                            spot_market_account,
                            margin_category,
                            liquidation_buffer,
                        )
                    )

                    net_quote_value -= weighted_token_value
                else:
                    weighted_token_value = self.get_spot_asset_value(
                        token_amount,
                        oracle_price_data,
                        spot_market_account,
                        margin_category,
                    )

                    net_quote_value += weighted_token_value

                continue

            if not include_open_orders and count_for_base:
                token_amount = get_signed_token_amount(
                    get_token_amount(
                        spot_position.scaled_balance,
                        spot_market_account,
                        spot_position.balance_type,
                    ),
                    spot_position.balance_type,
                )

                if is_variant(spot_position.balance_type, "Borrow"):
                    liability_value = abs(
                        self.get_spot_liability_value(
                            token_amount,
                            oracle_price_data,
                            spot_market_account,
                            margin_category,
                        )
                    )

                    total_liability_value += liability_value
                else:
                    asset_value = self.get_spot_asset_value(
                        token_amount,
                        oracle_price_data,
                        spot_market_account,
                        margin_category,
                    )

                    total_asset_value += asset_value

                continue

            order_fill_simulation = get_worst_case_token_amounts(
                spot_position, spot_market_account, oracle_price_data, margin_category
            )

            worst_case_token_amount, wort_case_orders_value = (
                order_fill_simulation.token_amount,
                order_fill_simulation.orders_value,
            )

            if worst_case_token_amount > 0 and count_for_base:
                asset_value = self.get_spot_asset_value(
                    worst_case_token_amount,
                    oracle_price_data,
                    spot_market_account,
                    margin_category,
                )

                total_asset_value += asset_value

            if worst_case_token_amount < 0 and count_for_base:
                liability_value = abs(
                    self.get_spot_liability_value(
                        worst_case_token_amount,
                        oracle_price_data,
                        spot_market_account,
                        margin_category,
                    )
                )

                total_liability_value += liability_value

            if wort_case_orders_value != 0 and count_for_quote:
                net_quote_value += wort_case_orders_value

        if market_index is None or market_index == QUOTE_SPOT_MARKET_INDEX:
            if net_quote_value > 0:
                total_asset_value += net_quote_value
            else:
                total_liability_value += abs(net_quote_value)

        return total_asset_value, total_liability_value

    def get_spot_asset_value(
        self,
        amount: int,
        oracle_price_data: OraclePriceData,
        spot_market: SpotMarketAccount,
        margin_category: MarginCategory,
    ):
        asset_value = get_token_value(amount, spot_market.decimals, oracle_price_data)

        if margin_category is not None:
            weight = calculate_asset_weight(
                amount, oracle_price_data.price, spot_market, margin_category
            )
            asset_value = asset_value * weight // SPOT_WEIGHT_PRECISION

        return asset_value

    def get_spot_liability_value(
        self,
        token_amount: int,
        oracle_data: OraclePriceData,
        spot_market: SpotMarketAccount,
        margin_category: MarginCategory,
        liquidation_buffer: int = None,
        max_margin_ratio: int = None,
    ) -> int:
        liability_value = get_token_value(
            token_amount, spot_market.decimals, oracle_data
        )

        if margin_category is not None:
            weight = calculate_liability_weight(
                token_amount, spot_market, margin_category
            )

            if margin_category == MarginCategory.INITIAL:
                if max_margin_ratio:
                    weight = max(weight, max_margin_ratio)

            if liquidation_buffer is not None:
                weight += liquidation_buffer

            liability_value = liability_value * weight // SPOT_WEIGHT_PRECISION

        return liability_value

    def get_spot_market_asset_value(
        self,
        market_index: Optional[int] = None,
        margin_category: Optional[MarginCategory] = None,
        include_open_orders=True,
    ):
        asset_value, _ = self.get_spot_market_asset_and_liability_value(
            market_index, margin_category, include_open_orders=include_open_orders
        )
        return asset_value

    def get_spot_market_liability(
        self,
        market_index=None,
        margin_category=None,
        liquidation_buffer=None,
        include_open_orders=None,
    ):
        _, liability_value = self.get_spot_market_asset_and_liability_value(
            market_index, margin_category, liquidation_buffer, include_open_orders
        )
        return liability_value

    def get_leverage(self, include_open_orders: bool = True) -> int:
        perp_liability = self.get_perp_market_liability(
            include_open_orders=include_open_orders
        )
        perp_pnl = self.get_unrealized_pnl(True)

        (
            spot_asset_value,
            spot_liability_value,
        ) = self.get_spot_market_asset_and_liability_value(
            include_open_orders=include_open_orders
        )

        total_asset_value = spot_asset_value + perp_pnl
        total_liability_value = spot_liability_value + perp_liability

        net_asset_value = total_asset_value - spot_liability_value

        if net_asset_value == 0:
            return 0

        return (total_liability_value * 10_000) // net_asset_value

    def get_perp_liq_price(
        self,
        perp_market_index: int,
    ) -> Optional[int]:
        position = self.get_user_position(perp_market_index)
        if position is None or position.base_asset_amount == 0:
            return None

        total_collateral = self.get_total_collateral(MarginCategory.MAINTENANCE)
        margin_req = self.get_margin_requirement(MarginCategory.MAINTENANCE)
        delta_liq = total_collateral - margin_req

        delta_per_baa = delta_liq / (position.base_asset_amount / AMM_RESERVE_PRECISION)

        oracle_price = (
            self.get_oracle_data_for_perp_market(perp_market_index).price
            / PRICE_PRECISION
        )

        liq_price = oracle_price - (delta_per_baa / QUOTE_PRECISION)
        if liq_price < 0:
            return None

        return liq_price

    def get_spot_liq_price(
        self,
        spot_market_index: int,
    ) -> Optional[int]:
        position = self.get_user_spot_position(spot_market_index)
        if position is None:
            return None

        total_collateral = self.get_total_collateral(MarginCategory.MAINTENANCE)
        margin_req = self.get_margin_requirement(
            MarginCategory.MAINTENANCE, None, True, False
        )
        delta_liq = total_collateral - margin_req

        spot_market = self.drift_client.get_spot_market_account(spot_market_index)
        token_amount = get_token_amount(
            position.scaled_balance, spot_market, position.balance_type
        )
        token_amount_qp = token_amount * QUOTE_PRECISION / (10**spot_market.decimals)
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

        price = self.drift_client.get_oracle_price_data(spot_market.oracle).price
        liq_price = price + liq_price_delta
        liq_price /= PRICE_PRECISION

        if liq_price < 0:
            return None

        return liq_price

    def get_empty_position(self, market_index: int) -> PerpPosition:
        return PerpPosition(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, market_index, 0, 0)

    def get_perp_position_with_lp_settle(
        self,
        market_index: int,
        originalPosition: PerpPosition = None,
        burnLpShares: bool = False,
        includeRemainderInBaseAmount: bool = False,
    ) -> Tuple[PerpPosition, int, int]:
        class UpdateType(Enum):
            OPEN = "open"
            INCREASE = "increase"
            REDUCE = "reduce"
            CLOSE = "close"
            FLIP = "flip"

        originalPosition = (
            originalPosition
            or self.get_perp_position(market_index)
            or self.get_empty_position(market_index)
        )

        if originalPosition.lp_shares == 0:
            return originalPosition, 0, 0

        position = copy.deepcopy(originalPosition)
        market = self.drift_client.get_perp_market_account(position.market_index)

        if market.amm.per_lp_base != position.per_lp_base:
            expoDiff = market.amm.per_lp_base - position.per_lp_base
            marketPerLpRebaseScalar = 10 ** abs(expoDiff)

            if expoDiff > 0:
                position.lastbase_asset_amount_per_lp *= marketPerLpRebaseScalar
                position.lastquote_asset_amount_per_lp *= marketPerLpRebaseScalar
            else:
                position.lastbase_asset_amount_per_lp //= marketPerLpRebaseScalar
                position.lastquote_asset_amount_per_lp //= marketPerLpRebaseScalar

            position.per_lp_base += expoDiff

        nShares = position.lp_shares

        quoteFundingPnl = calculate_position_funding_pnl(market, position)

        baseUnit = int(AMM_RESERVE_PRECISION)
        if market.amm.per_lp_base == position.per_lp_base:
            if 0 <= position.per_lp_base <= 9:
                marketPerLpRebase = 10**market.amm.per_lp_base
                baseUnit *= marketPerLpRebase
            elif position.per_lp_base < 0 and position.per_lp_base >= -9:
                marketPerLpRebase = 10 ** abs(position.per_lp_base)
                baseUnit //= marketPerLpRebase
            else:
                raise ValueError("cannot calc")
        else:
            raise ValueError("market.amm.perLpBase != position.perLpBase")

        deltaBaa = (
            (
                market.amm.base_asset_amount_per_lp
                - position.last_base_asset_amount_per_lp
            )
            * nShares
            // baseUnit
        )
        deltaQaa = (
            (
                market.amm.quote_asset_amount_per_lp
                - position.last_quote_asset_amount_per_lp
            )
            * nShares
            // baseUnit
        )

        def sign(v: int) -> int:
            return -1 if v < 0 else 1

        def standardize(amount: int, stepSize: int) -> Tuple[int, int]:
            remainder = abs(amount) % stepSize * sign(amount)
            standardizedAmount = amount - remainder
            return standardizedAmount, remainder

        standardizedBaa, remainderBaa = standardize(
            deltaBaa, market.amm.order_step_size
        )

        position.remainder_base_asset_amount += remainderBaa

        if abs(position.remainder_base_asset_amount) > market.amm.order_step_size:
            newStandardizedBaa, newRemainderBaa = standardize(
                position.remainder_base_asset_amount, market.amm.order_step_size
            )
            position.base_asset_amount += newStandardizedBaa
            position.remainder_base_asset_amount = newRemainderBaa

        dustBaseAssetValue = 0
        if burnLpShares and position.remainder_base_asset_amount != 0:
            oraclePriceData = self.drift_client.get_oracle_data_for_perp_market(
                position.market_index
            )
            dustBaseAssetValue = (
                abs(position.remainder_base_asset_amount)
                * oraclePriceData.price
                // AMM_RESERVE_PRECISION
                + 1
            )

        if position.base_asset_amount == 0:
            updateType = UpdateType.OPEN
        elif sign(position.base_asset_amount) == sign(deltaBaa):
            updateType = UpdateType.INCREASE
        elif abs(position.base_asset_amount) > abs(deltaBaa):
            updateType = UpdateType.REDUCE
        elif abs(position.base_asset_amount) == abs(deltaBaa):
            updateType = UpdateType.CLOSE
        else:
            updateType = UpdateType.FLIP

        if updateType in [UpdateType.OPEN, UpdateType.INCREASE]:
            newQuoteEntry = position.quote_entry_amount + deltaQaa
            pnl = 0
        elif updateType in [UpdateType.REDUCE, UpdateType.CLOSE]:
            newQuoteEntry = (
                position.quote_entry_amount
                - position.quote_entry_amount
                * abs(deltaBaa)
                // abs(position.base_asset_amount)
            )
            pnl = position.quote_entry_amount - newQuoteEntry + deltaQaa
        else:
            newQuoteEntry = deltaQaa - deltaQaa * abs(
                position.base_asset_amount
            ) // abs(deltaBaa)
            pnl = position.quote_entry_amount + deltaQaa - newQuoteEntry

        position.quote_entry_amount = newQuoteEntry
        position.base_asset_amount += standardizedBaa
        position.quote_asset_amount = (
            position.quote_asset_amount
            + deltaQaa
            + quoteFundingPnl
            - dustBaseAssetValue
        )
        position.quote_break_even_amount = (
            position.quote_break_even_amount
            + deltaQaa
            + quoteFundingPnl
            - dustBaseAssetValue
        )

        market_open_bids, market_open_asks = calculate_market_open_bid_ask(
            market.amm.base_asset_reserve,
            market.amm.min_base_asset_reserve,
            market.amm.max_base_asset_reserve,
            market.amm.order_step_size,
        )
        lp_open_bids = market_open_bids * position.lp_shares // market.amm.sqrt_k
        lp_open_asks = market_open_asks * position.lp_shares // market.amm.sqrt_k
        position.open_bids += lp_open_bids
        position.open_asks += lp_open_asks

        if position.base_asset_amount > 0:
            position.last_cumulative_funding_rate = (
                market.amm.cumulative_funding_rate_long
            )
        elif position.base_asset_amount < 0:
            position.last_cumulative_funding_rate = (
                market.amm.cumulative_funding_rate_short
            )
        else:
            position.last_cumulative_funding_rate = 0

        remainder_before_removal = position.remainder_base_asset_amount

        if includeRemainderInBaseAmount:
            position.base_asset_amount += remainder_before_removal
            position.remainder_base_asset_amount = 0

        return position, remainder_before_removal, pnl

    def get_net_spot_market_value(
        self, with_weight_margin_category: Optional[MarginCategory]
    ) -> int:
        (
            total_asset_value,
            total_liability_value,
        ) = self.get_spot_market_asset_and_liability_value(
            None, with_weight_margin_category
        )

        return total_asset_value - total_liability_value
