import math
import time
import copy

from typing import Tuple

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.math.amm import calculate_market_open_bid_ask
from driftpy.math.conversion import convert_to_number
from driftpy.math.oracles import calculate_live_oracle_twap
from driftpy.math.perp_position import *
from driftpy.math.margin import *
from driftpy.math.spot_balance import get_strict_token_value
from driftpy.math.spot_market import *
from driftpy.accounts.oracle import *
from driftpy.math.spot_position import (
    get_worst_case_token_amounts,
    is_spot_position_available,
)
from driftpy.math.amm import calculate_market_open_bid_ask
from driftpy.oracles.strict_oracle_price import StrictOraclePrice
from driftpy.types import OraclePriceData


class DriftUser:
    """This class is the main way to retrieve and inspect drift user account data."""

    def __init__(
        self,
        drift_client,
        user_public_key: Pubkey,
        account_subscription: Optional[
            AccountSubscriptionConfig
        ] = AccountSubscriptionConfig.default(),
    ):
        """Initialize the user object

        Args:
            drift_client(DriftClient): required for program_id, idl, things (keypair doesnt matter)
            user_public_key (Pubkey): pubkey for user account
            account_subscription (Optional[AccountSubscriptionConfig], optional): method of receiving account updates
        """
        from driftpy.drift_client import DriftClient

        self.drift_client: DriftClient = drift_client
        self.program = drift_client.program
        self.oracle_program = drift_client
        self.connection = self.program.provider.connection

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

            price = (self.get_oracle_data_for_perp_market(position.market_index)).price
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

    def is_being_liquidated(self) -> bool:
        user_account = self.get_user_account()
        return (
            user_account.status & (UserStatus.BEING_LIQUIDATED | UserStatus.BANKRUPT)
        ) > 0

    def can_be_liquidated(self) -> bool:
        total_collateral = self.get_total_collateral()

        user = self.get_user_account()
        liquidation_buffer = None
        if self.is_being_liquidated():
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
        strict: bool = False,
    ) -> int:
        total_perp_pos_value = self.get_total_perp_position_value(
            margin_category, liquidation_buffer, True, strict
        )
        spot_market_liab_value = self.get_spot_market_liability_value(
            None, margin_category, liquidation_buffer, True, strict
        )

        return total_perp_pos_value + spot_market_liab_value

    def get_total_perp_position_value(
        self,
        margin_category: Optional[MarginCategory] = None,
        liquidation_buffer: Optional[int] = None,
        include_open_orders: Optional[bool] = False,
        strict: bool = False,
    ) -> int:
        total_perp_value = 0
        for perp_position in self.get_active_perp_positions():
            base_asset_value = self.calculate_weighted_perp_position_value(
                perp_position,
                margin_category,
                liquidation_buffer,
                include_open_orders,
                strict,
            )
            total_perp_value += base_asset_value

        return total_perp_value

    def calculate_weighted_perp_position_value(
        self,
        perp_position: PerpPosition,
        margin_category: Optional[MarginCategory] = None,
        liquidation_buffer: Optional[int] = None,
        include_open_orders: Optional[bool] = False,
        strict: bool = False,
    ) -> int:
        market = self.drift_client.get_perp_market_account(perp_position.market_index)

        if perp_position.lp_shares > 0:
            perp_position = self.get_perp_position_with_lp_settle(
                market.market_index,
                copy.deepcopy(perp_position),
                margin_category is not None,
            )[0]

        valuation_price = self.get_oracle_data_for_perp_market(
            market.market_index
        ).price

        if is_variant(market.status, "Settlement"):
            valuation_price = market.expiry_price

        base_asset_amount = (
            calculate_worst_case_base_asset_amount(perp_position)
            if include_open_orders
            else perp_position.base_asset_amount
        )

        base_asset_value = (abs(base_asset_amount) * valuation_price) // BASE_PRECISION

        if margin_category is not None:
            margin_ratio = calculate_market_margin_ratio(
                market,
                abs(base_asset_amount),
                margin_category,
                self.get_user_account().max_margin_ratio,
            )

            if liquidation_buffer is not None:
                margin_ratio += liquidation_buffer

            if is_variant(market.status, "Settlement"):
                margin_ratio = 0

            quote_spot_market = self.drift_client.get_spot_market_account(
                market.quote_spot_market_index
            )

            quote_oracle_price_data = self.get_oracle_data_for_spot_market(
                QUOTE_SPOT_MARKET_INDEX
            )

            if strict:
                quote_price = max(
                    quote_oracle_price_data.price,
                    quote_spot_market.historical_oracle_data.last_oracle_price_twap5min,
                )
            else:
                quote_price = quote_oracle_price_data.price

            base_asset_value = (
                ((base_asset_value * quote_price) // PRICE_PRECISION) * margin_ratio
            ) // MARGIN_PRECISION

            if include_open_orders:
                base_asset_value += (
                    perp_position.open_orders * OPEN_ORDER_MARGIN_REQUIREMENT
                )

                if perp_position.lp_shares > 0:
                    base_asset_value += max(
                        QUOTE_PRECISION,
                        (
                            (
                                valuation_price
                                * market.amm.order_step_size
                                * QUOTE_PRECISION
                            )
                            // AMM_RESERVE_PRECISION
                        )
                        // PRICE_PRECISION,
                    )

        return base_asset_value

    def get_active_perp_positions(self) -> list[PerpPosition]:
        user = self.get_user_account()
        return self.get_active_perp_positions_for_user_account(user)

    def get_active_perp_positions_for_user_account(
        self, user: UserAccount
    ) -> list[PerpPosition]:
        return [
            pos
            for pos in user.perp_positions
            if pos.base_asset_amount != 0
            or pos.quote_asset_amount != 0
            or pos.open_orders != 0
            or pos.lp_shares != 0
        ]

    def get_total_collateral(
        self,
        margin_category: Optional[MarginCategory] = MarginCategory.INITIAL,
        strict: bool = False,
    ) -> int:
        asset_value = self.get_spot_market_asset_value(
            margin_category=margin_category, include_open_orders=True, strict=strict
        )
        pnl = self.get_unrealized_pnl(True, with_weight_margin_category=margin_category)
        total_collateral = asset_value + pnl
        return total_collateral

    def get_free_collateral(
        self, margin_category: MarginCategory = MarginCategory.INITIAL
    ):
        total_collateral = self.get_total_collateral(margin_category, True)
        if margin_category == MarginCategory.INITIAL:
            margin_req = self.get_margin_requirement(margin_category, strict=True)
        else:
            margin_req = self.get_margin_requirement(margin_category)
        free_collateral = total_collateral - margin_req
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

    def get_health(self) -> int:
        if self.is_being_liquidated():
            return 0

        total_collateral = self.get_total_collateral(MarginCategory.MAINTENANCE)
        maintenance_margin_req = self.get_margin_requirement(MarginCategory.MAINTENANCE)

        if maintenance_margin_req == 0 and total_collateral >= 0:
            return 100
        elif total_collateral <= 0:
            return 0
        else:
            return round(
                min(100, max(0, (1 - maintenance_margin_req / total_collateral) * 100))
            )

    def get_unrealized_pnl(
        self,
        with_funding: bool = False,
        market_index: int = None,
        with_weight_margin_category: Optional[MarginCategory] = None,
        strict: bool = False,
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

            oracle_price_data = self.get_oracle_data_for_perp_market(
                market.market_index
            )

            quote_oracle_price_data = self.get_oracle_data_for_spot_market(
                quote_spot_market.market_index
            )

            if position.lp_shares > 0:
                position = self.get_perp_position_with_lp_settle(
                    position.market_index, None, bool(with_weight_margin_category)
                )[0]

            position_upnl = calculate_position_pnl(
                market, position, oracle_price_data, with_funding
            )

            if strict and position_upnl > 0:
                quote_price = min(
                    quote_oracle_price_data.price,
                    quote_spot_market.historical_oracle_data.last_oracle_price_twap5min,
                )
            elif strict and position_upnl < 0:
                quote_price = max(
                    quote_oracle_price_data.price,
                    quote_spot_market.historical_oracle_data.last_oracle_price_twap5min,
                )
            else:
                quote_price = quote_oracle_price_data.price

            position_upnl = (position_upnl * quote_price) // PRICE_PRECISION

            if with_weight_margin_category:
                if position_upnl > 0:
                    position_upnl = position_upnl * (
                        calculate_unrealized_asset_weight(
                            market,
                            quote_spot_market,
                            position_upnl,
                            with_weight_margin_category,
                            oracle_price_data,
                        )
                    )
                    position_upnl = position_upnl // SPOT_MARKET_WEIGHT_PRECISION

            unrealized_pnl += position_upnl

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
        market_index: Optional[int] = None,
        margin_category: Optional[MarginCategory] = None,
        liquidation_buffer: Optional[int] = None,
        include_open_orders: bool = True,
        strict: bool = False,
        now: Optional[int] = None,
    ) -> (int, int):
        now = now or int(time.time())
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
            oracle_price_data = self.get_oracle_data_for_spot_market(
                spot_position.market_index
            )

            twap_5m = None
            if strict:
                twap_5m = calculate_live_oracle_twap(
                    spot_market_account.historical_oracle_data,
                    oracle_price_data,
                    now,
                    FIVE_MINUTE,
                )

            strict_oracle_price = StrictOraclePrice(oracle_price_data.price, twap_5m)

            if (
                spot_position.market_index == QUOTE_SPOT_MARKET_INDEX
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
                            strict_oracle_price,
                            spot_market_account,
                            margin_category,
                            liquidation_buffer,
                        )
                    )
                    net_quote_value -= weighted_token_value
                else:
                    weighted_token_value = self.get_spot_asset_value(
                        token_amount,
                        strict_oracle_price,
                        spot_market_account,
                        margin_category,
                    )
                    net_quote_value += weighted_token_value
                continue

            if not include_open_orders and count_for_base:
                if is_variant(spot_position.balance_type, "Borrow"):
                    token_amount = get_signed_token_amount(
                        get_token_amount(
                            spot_position.scaled_balance,
                            spot_market_account,
                            spot_position.balance_type,
                        ),
                        "Borrow",
                    )
                    liability_value = abs(
                        self.get_spot_liability_value(
                            token_amount,
                            strict_oracle_price,
                            spot_market_account,
                            margin_category,
                            liquidation_buffer,
                        )
                    )
                    total_liability_value += liability_value
                else:
                    token_amount = get_token_amount(
                        spot_position.scaled_balance,
                        spot_market_account,
                        spot_position.balance_type,
                    )
                    asset_value = self.get_spot_asset_value(
                        token_amount,
                        strict_oracle_price,
                        spot_market_account,
                        margin_category,
                    )
                    total_asset_value += asset_value
                continue

            order_fill_simulation = get_worst_case_token_amounts(
                spot_position,
                spot_market_account,
                strict_oracle_price,
                margin_category,
                self.get_user_account().max_margin_ratio,
            )
            worst_case_token_amount = order_fill_simulation.token_amount
            worst_case_quote_token_amount = order_fill_simulation.orders_value

            if worst_case_token_amount > 0 and count_for_base:
                base_asset_value = self.get_spot_asset_value(
                    worst_case_token_amount,
                    strict_oracle_price,
                    spot_market_account,
                    margin_category,
                )
                total_asset_value += base_asset_value

            if worst_case_token_amount < 0 and count_for_base:
                base_liability_value = abs(
                    self.get_spot_liability_value(
                        worst_case_token_amount,
                        strict_oracle_price,
                        spot_market_account,
                        margin_category,
                        liquidation_buffer,
                    )
                )
                total_liability_value += base_liability_value

            if worst_case_quote_token_amount > 0 and count_for_quote:
                net_quote_value += worst_case_quote_token_amount

            if worst_case_quote_token_amount < 0 and count_for_quote:
                weight = SPOT_MARKET_WEIGHT_PRECISION
                if margin_category == MarginCategory.INITIAL:
                    weight = max(weight, self.get_user_account().max_margin_ratio)
                weighted_token_value = (
                    abs(worst_case_quote_token_amount)
                    * weight
                    // SPOT_MARKET_WEIGHT_PRECISION
                )
                net_quote_value -= weighted_token_value

            total_liability_value += (
                spot_position.open_orders * OPEN_ORDER_MARGIN_REQUIREMENT
            )

        if market_index is None or market_index == QUOTE_SPOT_MARKET_INDEX:
            if net_quote_value > 0:
                total_asset_value += net_quote_value
            else:
                total_liability_value += abs(net_quote_value)

        return total_asset_value, total_liability_value

    def get_spot_asset_value(
        self,
        token_amount: int,
        strict_oracle_price: StrictOraclePrice,
        spot_market_account: SpotMarketAccount,
        margin_category: Optional[MarginCategory] = None,
    ) -> int:
        asset_value = get_strict_token_value(
            token_amount, spot_market_account.decimals, strict_oracle_price
        )

        if margin_category is not None:
            weight = calculate_asset_weight(
                token_amount,
                strict_oracle_price.current,
                spot_market_account,
                margin_category,
            )

            if (
                margin_category == MarginCategory.INITIAL
                and spot_market_account.market_index != QUOTE_SPOT_MARKET_INDEX
            ):
                user_custom_asset_weight = max(
                    0,
                    SPOT_MARKET_WEIGHT_PRECISION
                    - self.get_user_account().max_margin_ratio,
                )
                weight = min(weight, user_custom_asset_weight)

            asset_value = (asset_value * weight) // SPOT_MARKET_WEIGHT_PRECISION

        return asset_value

    def get_spot_liability_value(
        self,
        token_amount: int,
        strict_oracle_price: StrictOraclePrice,
        spot_market_account: SpotMarketAccount,
        margin_category: Optional[MarginCategory] = None,
        liquidation_buffer: Optional[int] = None,
    ) -> int:
        liability_value = get_strict_token_value(
            token_amount, spot_market_account.decimals, strict_oracle_price
        )

        if margin_category is not None:
            weight = calculate_liability_weight(
                token_amount, spot_market_account, margin_category
            )

            if (
                margin_category == MarginCategory.INITIAL
                and spot_market_account.market_index != QUOTE_SPOT_MARKET_INDEX
            ):
                weight = max(
                    weight,
                    SPOT_MARKET_WEIGHT_PRECISION
                    + self.get_user_account().max_margin_ratio,
                )

            if liquidation_buffer is not None:
                weight += liquidation_buffer

            liability_value = (liability_value * weight) // SPOT_MARKET_WEIGHT_PRECISION

        return liability_value

    def get_spot_market_asset_value(
        self,
        market_index: Optional[int] = None,
        margin_category: Optional[MarginCategory] = None,
        include_open_orders: bool = True,
        strict: bool = False,
        now: Optional[int] = None,
    ):
        asset_value, _ = self.get_spot_market_asset_and_liability_value(
            market_index,
            margin_category,
            include_open_orders=include_open_orders,
            strict=strict,
            now=now,
        )
        return asset_value

    def get_spot_market_liability_value(
        self,
        market_index: Optional[int] = None,
        margin_category: Optional[MarginCategory] = None,
        liquidation_buffer: Optional[int] = None,
        include_open_orders: bool = True,
        strict: bool = False,
        now: Optional[int] = None,
    ):
        _, total_liability_value = self.get_spot_market_asset_and_liability_value(
            market_index,
            margin_category,
            liquidation_buffer,
            include_open_orders,
            strict,
            now,
        )
        return total_liability_value

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

    def get_leverage_components(
        self,
        include_open_orders: bool = True,
        margin_category: Optional[MarginCategory] = None,
    ):
        perp_liability = self.get_total_perp_position_value(
            margin_category, None, include_open_orders
        )

        perp_pnl = self.get_unrealized_pnl(True, None, margin_category)

        (
            spot_asset_value,
            spot_liability_value,
        ) = self.get_spot_market_asset_and_liability_value(
            None, margin_category, None, include_open_orders
        )

        return perp_liability, perp_pnl, spot_asset_value, spot_liability_value

    def get_max_leverage_for_perp(
        self,
        perp_market_index: int,
        margin_category: MarginCategory = MarginCategory.INITIAL,
        is_lp: bool = False,
    ):
        market = self.drift_client.get_perp_market_account(perp_market_index)
        market_price = self.drift_client.get_oracle_price_data_for_perp_market(
            perp_market_index
        ).price

        perp_liab, perp_pnl, spot_asset, spot_liab = self.get_leverage_components()

        total_assets = spot_asset + perp_pnl

        net_assets = total_assets - spot_liab

        if net_assets == 0:
            return 0

        total_liabs = perp_liab + spot_liab

        lp_buffer = (
            math.ceil(market_price * market.amm.order_step_size / AMM_RESERVE_PRECISION)
            if is_lp
            else 0
        )

        free_collateral = self.get_free_collateral() - lp_buffer

        match margin_category:
            case MarginCategory.INITIAL:
                raw_margin_ratio = max(
                    market.margin_ratio_initial,
                    self.get_user_account().max_margin_ratio,
                )
            case MarginCategory.MAINTENANCE:
                raw_margin_ratio = market.margin_ratio_maintenance
            case _:
                raw_margin_ratio = market.margin_ratio_initial

        # upper bound for feasible sizing
        rhs = (
            math.ceil(
                ((free_collateral * MARGIN_PRECISION) / raw_margin_ratio)
                * PRICE_PRECISION
            )
        ) / market_price
        max_size = max(0, rhs)

        # accounting for max size
        margin_ratio = calculate_market_margin_ratio(
            market, max_size, margin_category, self.get_user_account().max_margin_ratio
        )

        attempts = 0
        while margin_ratio > (raw_margin_ratio + 1e-4) and attempts < 10:
            rhs = math.ceil(
                (
                    ((free_collateral * MARGIN_PRECISION) / margin_ratio)
                    * PRICE_PRECISION
                )
                / market_price
            )

            target_size = max(0, rhs)

            margin_ratio = calculate_market_margin_ratio(
                market,
                target_size,
                margin_category,
                self.get_user_account().max_margin_ratio,
            )

            attempts += 1

        additional_liab = math.ceil((free_collateral * MARGIN_PRECISION) / margin_ratio)

        return math.ceil(((total_liabs + additional_liab) * 10_000) / net_assets)

    def calculate_free_collateral_delta_for_perp(
        self,
        market: PerpMarketAccount,
        perp_position: PerpPosition,
        position_base_size_change: int,
    ) -> Union[int, None]:
        current_base_asset_amt = perp_position.base_asset_amount

        worst_case_base_asset_amt = calculate_worst_case_base_asset_amount(
            perp_position
        )

        order_base_asset_amt = worst_case_base_asset_amt - current_base_asset_amt

        proposed_base_asset_amt = current_base_asset_amt + position_base_size_change

        proposed_worst_case_base_asset_amt = (
            worst_case_base_asset_amt + position_base_size_change
        )

        margin_ratio = calculate_market_margin_ratio(
            market, abs(proposed_worst_case_base_asset_amt), MarginCategory.MAINTENANCE
        )

        margin_ratio_quote_precision = (
            margin_ratio * QUOTE_PRECISION
        ) // MARGIN_PRECISION

        if proposed_worst_case_base_asset_amt == 0:
            return None

        free_collateral_delta = 0
        if proposed_base_asset_amt > 0:
            free_collateral_delta = (
                (QUOTE_PRECISION - margin_ratio_quote_precision)
                * proposed_base_asset_amt
            ) // BASE_PRECISION
        else:
            free_collateral_delta = (
                (-QUOTE_PRECISION - margin_ratio_quote_precision)
                * abs(proposed_base_asset_amt)
            ) // BASE_PRECISION

        if not order_base_asset_amt == 0:
            free_collateral_delta = free_collateral_delta - (
                margin_ratio_quote_precision
                * abs(order_base_asset_amt)
                // BASE_PRECISION
            )

        return free_collateral_delta

    def calculate_free_collateral_delta_for_spot(
        self, market: SpotMarketAccount, signed_token_amount: int
    ) -> int:
        token_precision = 10**market.decimals

        if signed_token_amount > 0:
            asset_weight = calculate_asset_weight(
                signed_token_amount,
                self.get_oracle_data_for_spot_market(market.market_index).price,
                market,
                MarginCategory.MAINTENANCE,
            )

            return (
                ((QUOTE_PRECISION * asset_weight) // SPOT_MARKET_WEIGHT_PRECISION)
                * signed_token_amount
            ) // token_precision

        else:
            liability_weight = calculate_liability_weight(
                abs(signed_token_amount), market, MarginCategory.MAINTENANCE
            )

            return (
                ((-QUOTE_PRECISION * liability_weight) // SPOT_MARKET_WEIGHT_PRECISION)
                * abs(signed_token_amount)
            ) // token_precision

    def get_perp_liq_price(
        self, perp_market_index: int, position_base_size_change: int = 0
    ) -> Optional[int]:
        total_collateral = self.get_total_collateral(MarginCategory.MAINTENANCE)
        maintenance_margin_req = self.get_margin_requirement(MarginCategory.MAINTENANCE)
        free_collateral = max(0, total_collateral - maintenance_margin_req)

        market = self.drift_client.get_perp_market_account(perp_market_index)
        current_perp_pos = self.get_perp_position_with_lp_settle(
            perp_market_index, burn_lp_shares=True
        )[0] or self.get_empty_position(perp_market_index)

        free_collateral_delta = self.calculate_free_collateral_delta_for_perp(
            market, current_perp_pos, position_base_size_change
        )

        if not free_collateral_delta:
            return -1

        oracle = market.amm.oracle

        sister_market = None
        for market in self.drift_client.get_spot_market_accounts():
            if market.oracle == oracle:
                sister_market = market
                break

        if sister_market:
            spot_position = self.get_spot_position(sister_market.market_index)
            if spot_position:
                signed_token_amount = get_signed_token_amount(
                    get_token_amount(
                        spot_position.scaled_balance,
                        sister_market,
                        spot_position.balance_type,
                    ),
                    spot_position.balance_type,
                )

                spot_free_collateral_delta = (
                    self.calculate_free_collateral_delta_for_spot(
                        sister_market, signed_token_amount
                    )
                )

                free_collateral_delta = (
                    free_collateral_delta + spot_free_collateral_delta
                )

        if free_collateral_delta == 0:
            return -1

        oracle_price = self.drift_client.get_oracle_price_data_for_perp_market(
            perp_market_index
        ).price

        liq_price_delta = (free_collateral * QUOTE_PRECISION) // free_collateral_delta

        liq_price = oracle_price - liq_price_delta

        if liq_price < 0:
            return -1

        return liq_price

    def get_spot_liq_price(
        self,
        spot_market_index: int,
    ) -> Optional[int]:
        position = self.get_user_spot_position(spot_market_index)
        if position is None:
            return None

        total_collateral = self.get_total_collateral(MarginCategory.MAINTENANCE)
        margin_req = self.get_margin_requirement(MarginCategory.MAINTENANCE, None, True)
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

        price = self.get_oracle_data_for_spot_market(spot_market.market_index).price
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
        original_position: PerpPosition = None,
        burn_lp_shares: bool = False,
        include_remainder_in_base_amount: bool = False,
    ) -> Tuple[PerpPosition, int, int]:
        class UpdateType(Enum):
            OPEN = "open"
            INCREASE = "increase"
            REDUCE = "reduce"
            CLOSE = "close"
            FLIP = "flip"

        original_position = (
            original_position
            or self.get_perp_position(market_index)
            or self.get_empty_position(market_index)
        )

        if original_position.lp_shares == 0:
            return original_position, 0, 0

        position = copy.deepcopy(original_position)
        market = self.drift_client.get_perp_market_account(position.market_index)

        if market.amm.per_lp_base != position.per_lp_base:
            expo_diff = market.amm.per_lp_base - position.per_lp_base
            market_per_lp_rebase_scalar = 10 ** abs(expo_diff)

            if expo_diff > 0:
                position.last_base_asset_amount_per_lp *= market_per_lp_rebase_scalar
                position.last_quote_asset_amount_per_lp *= market_per_lp_rebase_scalar
            else:
                position.last_base_asset_amount_per_lp //= market_per_lp_rebase_scalar
                position.last_quote_asset_amount_per_lp //= market_per_lp_rebase_scalar

            position.per_lp_base += expo_diff

        n_shares = position.lp_shares

        quote_funding_pnl = calculate_position_funding_pnl(market, position)

        base_unit = int(AMM_RESERVE_PRECISION)
        if market.amm.per_lp_base == position.per_lp_base:
            if 0 <= position.per_lp_base <= 9:
                market_per_lp_rebase = 10**market.amm.per_lp_base
                base_unit *= market_per_lp_rebase
            elif position.per_lp_base < 0 and position.per_lp_base >= -9:
                market_per_lp_rebase = 10 ** abs(position.per_lp_base)
                base_unit //= market_per_lp_rebase
            else:
                raise ValueError("cannot calc")
        else:
            raise ValueError("market.amm.per_lp_base != position.per_lp_base")

        delta_baa = (
            (
                market.amm.base_asset_amount_per_lp
                - position.last_base_asset_amount_per_lp
            )
            * n_shares
            // base_unit
        )
        delta_qaa = (
            (
                market.amm.quote_asset_amount_per_lp
                - position.last_quote_asset_amount_per_lp
            )
            * n_shares
            // base_unit
        )

        def sign(v: int) -> int:
            return -1 if v < 0 else 1

        def standardize(amount: int, step_size: int) -> Tuple[int, int]:
            remainder = abs(amount) % step_size * sign(amount)
            standardized_amount = amount - remainder
            return standardized_amount, remainder

        standardized_baa, remainder_baa = standardize(
            delta_baa, market.amm.order_step_size
        )

        position.remainder_base_asset_amount += remainder_baa

        if abs(position.remainder_base_asset_amount) > market.amm.order_step_size:
            new_standardized_baa, new_remainder_baa = standardize(
                position.remainder_base_asset_amount, market.amm.order_step_size
            )
            position.base_asset_amount += new_standardized_baa
            position.remainder_base_asset_amount = new_remainder_baa

        dust_base_asset_value = 0
        if burn_lp_shares and position.remainder_base_asset_amount != 0:
            oracle_price_data = self.drift_client.get_oracle_price_data_for_perp_market(
                position.market_index
            )
            dust_base_asset_value = (
                abs(position.remainder_base_asset_amount)
                * oracle_price_data.price
                // AMM_RESERVE_PRECISION
                + 1
            )

        if position.base_asset_amount == 0:
            update_type = UpdateType.OPEN
        elif sign(position.base_asset_amount) == sign(delta_baa):
            update_type = UpdateType.INCREASE
        elif abs(position.base_asset_amount) > abs(delta_baa):
            update_type = UpdateType.REDUCE
        elif abs(position.base_asset_amount) == abs(delta_baa):
            update_type = UpdateType.CLOSE
        else:
            update_type = UpdateType.FLIP

        if update_type in [UpdateType.OPEN, UpdateType.INCREASE]:
            new_quote_entry = position.quote_entry_amount + delta_qaa
            pnl = 0
        elif update_type in [UpdateType.REDUCE, UpdateType.CLOSE]:
            new_quote_entry = (
                position.quote_entry_amount
                - position.quote_entry_amount
                * abs(delta_baa)
                // abs(position.base_asset_amount)
            )
            pnl = position.quote_entry_amount - new_quote_entry + delta_qaa
        else:
            new_quote_entry = delta_qaa - delta_qaa * abs(
                position.base_asset_amount
            ) // abs(delta_baa)
            pnl = position.quote_entry_amount + delta_qaa - new_quote_entry

        position.quote_entry_amount = new_quote_entry
        position.base_asset_amount += standardized_baa
        position.quote_asset_amount = (
            position.quote_asset_amount
            + delta_qaa
            + quote_funding_pnl
            - dust_base_asset_value
        )
        position.quote_break_even_amount = (
            position.quote_break_even_amount
            + delta_qaa
            + quote_funding_pnl
            - dust_base_asset_value
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

        if include_remainder_in_base_amount:
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
