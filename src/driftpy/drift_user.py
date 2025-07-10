import copy
import math
import time
from enum import Enum
from typing import Optional, Tuple

from solders.pubkey import Pubkey

from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.accounts import (
    DataAndSlot,
    OraclePriceData,
    PerpMarketAccount,
    SpotMarketAccount,
    UserAccount,
)
from driftpy.constants import BASE_PRECISION, PRICE_PRECISION
from driftpy.constants.numeric_constants import (
    AMM_RESERVE_PRECISION,
    FIVE_MINUTE,
    FUEL_START_TS,
    GOV_SPOT_MARKET_INDEX,
    MARGIN_PRECISION,
    OPEN_ORDER_MARGIN_REQUIREMENT,
    QUOTE_PRECISION,
    QUOTE_SPOT_MARKET_INDEX,
    SPOT_MARKET_WEIGHT_PRECISION,
)
from driftpy.math.amm import calculate_market_open_bid_ask
from driftpy.math.fuel import (
    calculate_insurance_fuel_bonus,
    calculate_perp_fuel_bonus,
    calculate_spot_fuel_bonus,
)
from driftpy.math.margin import (
    MarginCategory,
    calculate_asset_weight,
    calculate_liability_weight,
    calculate_market_margin_ratio,
    calculate_unrealized_asset_weight,
)
from driftpy.math.oracles import calculate_live_oracle_twap
from driftpy.math.perp_position import (
    calculate_base_asset_value_with_oracle,
    calculate_perp_liability_value,
    calculate_position_funding_pnl,
    calculate_position_pnl,
    calculate_worst_case_base_asset_amount,
    calculate_worst_case_perp_liability_value,
    is_available,
)
from driftpy.math.spot_balance import get_strict_token_value, get_token_value
from driftpy.math.spot_market import get_signed_token_amount, get_token_amount
from driftpy.math.spot_position import (
    calculate_weighted_token_value,
    get_worst_case_token_amounts,
    is_spot_position_available,
)
from driftpy.oracles.strict_oracle_price import StrictOraclePrice
from driftpy.types import (
    Order,
    PerpPosition,
    SpotPosition,
    UserStatus,
    is_variant,
)


class DriftUser:
    """This class is the main way to retrieve and inspect drift user account data."""

    def __init__(
        self,
        drift_client,
        user_public_key: Pubkey,
        account_subscription: AccountSubscriptionConfig = AccountSubscriptionConfig.default(),
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
        if self.account_subscriber is None:
            raise ValueError("No account subscriber found")
        await self.account_subscriber.subscribe()

    def unsubscribe(self):
        if self.account_subscriber is None:
            raise ValueError("No account subscriber found")
        self.account_subscriber.unsubscribe()

    def get_oracle_data_for_spot_market(
        self, market_index: int
    ) -> OraclePriceData | None:
        return self.drift_client.get_oracle_price_data_for_spot_market(market_index)

    def get_oracle_data_for_perp_market(
        self, market_index: int
    ) -> OraclePriceData | None:
        return self.drift_client.get_oracle_price_data_for_perp_market(market_index)

    def get_perp_market_account(self, market_index: int) -> Optional[PerpMarketAccount]:
        return self.drift_client.get_perp_market_account(market_index)

    def get_spot_market_account(self, market_index: int) -> Optional[SpotMarketAccount]:
        return self.drift_client.get_spot_market_account(market_index)

    def get_user_account_and_slot(self) -> Optional[DataAndSlot[UserAccount]]:
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
            if order.user_order_id == user_order_id and is_variant(
                order.status, "Open"
            ):
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
            if position.market_index == market_index and not is_spot_position_available(
                position
            ):
                return position

        return None

    def get_perp_market_liability(
        self,
        market_index: int,
        margin_category: Optional[MarginCategory] = None,
        liquidation_buffer: Optional[int] = 0,
        include_open_orders: bool = False,
        signed: bool = False,
    ):
        perp_position = self.get_perp_position(market_index)
        if perp_position is None:
            return 0

        return self.calculate_weighted_perp_position_liability(
            perp_position,
            margin_category,
            liquidation_buffer,
            include_open_orders,
            signed,
        )

    def is_high_leverage_mode(self) -> bool:
        return is_variant(self.get_user_account().margin_mode, "HighLeverage")

    def is_being_liquidated(self) -> bool:
        user_account = self.get_user_account()
        return (
            user_account.status & (UserStatus.BEING_LIQUIDATED | UserStatus.BANKRUPT)
        ) > 0

    def can_be_liquidated(self) -> bool:
        total_collateral = self.get_total_collateral()

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
        total_perp_pos_value = self.get_total_perp_position_liability(
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

    def get_active_spot_positions(self) -> list[SpotPosition]:
        user = self.get_user_account()
        return self.get_active_spot_positions_for_user_account(user)

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

    def get_active_spot_positions_for_user_account(
        self, user: UserAccount
    ) -> list[SpotPosition]:
        return [
            spot_position
            for spot_position in user.spot_positions
            if not is_spot_position_available(spot_position)
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
            if position.market_index == market_index and not is_spot_position_available(
                position
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

    def get_health_components(
        self, margin_category: MarginCategory = MarginCategory.INITIAL
    ):
        health_components = {
            "deposits": [],
            "borrows": [],
            "perp_positions": [],
            "perp_pnl": [],
        }

        for perp_position in self.get_active_perp_positions():
            perp_market = self.drift_client.get_perp_market_account(
                perp_position.market_index
            )

            oracle_price_data = self.drift_client.get_oracle_price_data_for_perp_market(
                perp_market.market_index
            )

            quote_oracle_price_data = (
                self.drift_client.get_oracle_price_data_for_spot_market(
                    QUOTE_SPOT_MARKET_INDEX
                )
            )

            health_components["perp_positions"].append(
                self.get_perp_position_health(
                    margin_category=margin_category,
                    perp_position=perp_position,
                    oracle_price_data=oracle_price_data,
                    quote_oracle_price_data=quote_oracle_price_data,
                )
            )

            quote_spot_market = self.drift_client.get_spot_market_account(
                perp_market.quote_spot_market_index
            )

            settled_perp_position = self.get_perp_position_with_lp_settle(
                perp_position.market_index, perp_position
            )[0]

            position_unrealized_pnl = calculate_position_pnl(
                perp_market,
                settled_perp_position,
                oracle_price_data,
                True,  # with_funding=True
            )

            if position_unrealized_pnl > 0:
                pnl_weight = calculate_unrealized_asset_weight(
                    perp_market,
                    quote_spot_market,
                    position_unrealized_pnl,
                    margin_category,
                    oracle_price_data,
                )
            else:
                pnl_weight = SPOT_MARKET_WEIGHT_PRECISION

            pnl_value = (
                position_unrealized_pnl * quote_oracle_price_data.price
            ) // PRICE_PRECISION
            weighted_pnl_value = (
                pnl_value * pnl_weight
            ) // SPOT_MARKET_WEIGHT_PRECISION

            health_components["perp_pnl"].append(
                {
                    "market_index": perp_market.market_index,
                    "size": position_unrealized_pnl,
                    "value": pnl_value,
                    "weight": pnl_weight,
                    "weighted_value": weighted_pnl_value,
                }
            )

        # Process spot positions and continue with the rest...
        net_quote_value = 0
        for spot_position in self.get_active_spot_positions():
            spot_market_account = self.drift_client.get_spot_market_account(
                spot_position.market_index
            )

            oracle_price_data = self.get_oracle_data_for_spot_market(
                spot_position.market_index
            )

            strict_oracle_price = StrictOraclePrice(oracle_price_data.price)

            if spot_position.market_index == QUOTE_SPOT_MARKET_INDEX:
                token_amount = get_signed_token_amount(
                    get_token_amount(
                        spot_position.scaled_balance,
                        spot_market_account,
                        spot_position.balance_type,
                    ),
                    spot_position.balance_type,
                )
                net_quote_value += token_amount
                continue

            order_fill_simulation = get_worst_case_token_amounts(
                spot_position,
                spot_market_account,
                strict_oracle_price,
                margin_category,
                self.get_user_account().max_margin_ratio,
            )

            worst_case_token_amount = order_fill_simulation.token_amount
            token_value = order_fill_simulation.token_value
            weight = order_fill_simulation.weight
            weighted_token_value = order_fill_simulation.weighted_token_value
            orders_value = order_fill_simulation.orders_value

            net_quote_value += orders_value

            base_asset_value = abs(token_value)
            weighted_value = abs(weighted_token_value)

            if weighted_token_value < 0:
                health_components["borrows"].append(
                    {
                        "market_index": spot_market_account.market_index,
                        "size": worst_case_token_amount,
                        "value": base_asset_value,
                        "weight": weight,
                        "weighted_value": weighted_value,
                    }
                )
            else:
                health_components["deposits"].append(
                    {
                        "market_index": spot_market_account.market_index,
                        "size": worst_case_token_amount,
                        "value": base_asset_value,
                        "weight": weight,
                        "weighted_value": weighted_value,
                    }
                )

        if net_quote_value != 0:
            spot_market_account = self.drift_client.get_spot_market_account(
                QUOTE_SPOT_MARKET_INDEX
            )
            oracle_price_data = self.get_oracle_data_for_spot_market(
                QUOTE_SPOT_MARKET_INDEX
            )

            base_asset_value = get_token_value(
                net_quote_value, spot_market_account.decimals, oracle_price_data
            )

            weight, weighted_token_value = calculate_weighted_token_value(
                net_quote_value,
                base_asset_value,
                oracle_price_data.price,
                spot_market_account,
                margin_category,
                self.get_user_account().max_margin_ratio,
            )

            if net_quote_value < 0:
                health_components["borrows"].append(
                    {
                        "market_index": spot_market_account.market_index,
                        "size": net_quote_value,
                        "value": abs(base_asset_value),
                        "weight": weight,
                        "weighted_value": abs(weighted_token_value),
                    }
                )
            else:
                health_components["deposits"].append(
                    {
                        "market_index": spot_market_account.market_index,
                        "size": net_quote_value,
                        "value": base_asset_value,
                        "weight": weight,
                        "weighted_value": weighted_token_value,
                    }
                )

        return health_components

    def get_perp_position_health(
        self,
        margin_category: MarginCategory,
        perp_position: PerpPosition,
        oracle_price_data: Optional[OraclePriceData] = None,
        quote_oracle_price_data: Optional[OraclePriceData] = None,
    ):
        settled_lp_position = self.get_perp_position_with_lp_settle(
            perp_position.market_index, perp_position
        )[0]

        perp_market = self.drift_client.get_perp_market_account(
            perp_position.market_index
        )

        _oracle_price_data = (
            oracle_price_data
            or self.drift_client.get_oracle_data_for_perp_market(
                perp_market.market_index
            )
        )

        oracle_price = _oracle_price_data.price

        worst_case = calculate_worst_case_perp_liability_value(
            settled_lp_position, perp_market, oracle_price
        )
        worst_case_base_amount = worst_case["worst_case_base_asset_amount"]
        worst_case_liability_value = worst_case["worst_case_liability_value"]

        margin_ratio = calculate_market_margin_ratio(
            perp_market,
            abs(worst_case_base_amount),
            margin_category,
            self.get_user_account().max_margin_ratio,
            self.is_high_leverage_mode(),
        )

        _quote_oracle_price_data = (
            quote_oracle_price_data
            or self.drift_client.get_oracle_data_for_spot_market(
                QUOTE_SPOT_MARKET_INDEX
            )
        )

        margin_requirement = (
            (worst_case_liability_value * _quote_oracle_price_data.price)
            // PRICE_PRECISION
            * margin_ratio
            // MARGIN_PRECISION
        )

        margin_requirement += perp_position.open_orders * OPEN_ORDER_MARGIN_REQUIREMENT

        if perp_position.lp_shares > 0:
            margin_requirement += max(
                QUOTE_PRECISION,
                (
                    oracle_price
                    * perp_market.amm.order_step_size
                    * QUOTE_PRECISION
                    // AMM_RESERVE_PRECISION
                )
                // PRICE_PRECISION,
            )

        return {
            "market_index": perp_market.market_index,
            "size": worst_case_base_amount,
            "value": worst_case_liability_value,
            "weight": margin_ratio,
            "weighted_value": margin_requirement,
        }

    def get_settled_perp_pnl(self) -> int:
        user = self.get_user_account()
        return user.settled_perp_pnl

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
        market_index: Optional[int] = None,
    ):
        user = self.get_user_account()

        unrealized_pnl = 0
        for position in user.perp_positions:
            if market_index is not None and position.market_index != market_index:
                continue

            perp_market = self.drift_client.get_perp_market_account(
                position.market_index
            )
            if not perp_market:
                raise Exception("Perp market account not found")

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
        leverage_components = self.get_leverage_components(include_open_orders)
        return self.calculate_leverage_from_components(leverage_components)

    def get_leverage_components(
        self,
        include_open_orders: bool = True,
        margin_category: Optional[MarginCategory] = None,
    ):
        perp_liability = self.get_total_perp_position_liability(
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

    def calculate_leverage_from_components(self, components: Tuple[int, int, int, int]):
        perp_liability, perp_pnl, spot_asset_value, spot_liability_value = components

        total_liabs = perp_liability + spot_liability_value
        total_assets = spot_asset_value + perp_pnl
        net_assets = total_assets - spot_liability_value

        if net_assets == 0:
            return 0

        return (total_liabs * 10_000) // net_assets

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
        oracle_price: int,
        margin_category: MarginCategory = MarginCategory.MAINTENANCE,
        include_open_orders: bool = False,
    ) -> Optional[int]:
        base_asset_amount = (
            calculate_worst_case_base_asset_amount(perp_position, market, oracle_price)
            if include_open_orders
            else perp_position.base_asset_amount
        )
        # zero if include_orders == False
        order_base_asset_amount = base_asset_amount - perp_position.base_asset_amount
        proposed_base_asset_amount = base_asset_amount + position_base_size_change

        margin_ratio = calculate_market_margin_ratio(
            market,
            abs(proposed_base_asset_amount),
            margin_category,
            self.get_user_account().max_margin_ratio,
        )
        margin_ratio_quote_precision = (
            margin_ratio * QUOTE_PRECISION
        ) // MARGIN_PRECISION

        if proposed_base_asset_amount == 0:
            return None

        free_collateral_delta = 0

        if is_variant(market.contract_type, "Prediction"):
            # for prediction market, increase in pnl and margin requirement will net out for position
            # open order margin requirement will change with price though
            if order_base_asset_amount > 0:
                free_collateral_delta = -margin_ratio_quote_precision
            elif order_base_asset_amount < 0:
                free_collateral_delta = margin_ratio_quote_precision
        else:
            if proposed_base_asset_amount > 0:
                free_collateral_delta = (
                    (QUOTE_PRECISION - margin_ratio_quote_precision)
                    * proposed_base_asset_amount
                    // BASE_PRECISION
                )
            else:
                free_collateral_delta = (
                    (-QUOTE_PRECISION - margin_ratio_quote_precision)
                    * abs(proposed_base_asset_amount)
                    // BASE_PRECISION
                )

            if order_base_asset_amount != 0:
                free_collateral_delta -= (
                    margin_ratio_quote_precision
                    * abs(order_base_asset_amount)
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
        self,
        perp_market_index: int,
        position_base_size_change: int = 0,
        margin_category: MarginCategory = MarginCategory.MAINTENANCE,
    ) -> Optional[int]:
        total_collateral = self.get_total_collateral(margin_category)
        maintenance_margin_req = self.get_margin_requirement(margin_category)
        free_collateral = max(0, total_collateral - maintenance_margin_req)

        market = self.drift_client.get_perp_market_account(perp_market_index)
        current_perp_pos = self.get_perp_position_with_lp_settle(
            perp_market_index, burn_lp_shares=True
        )[0] or self.get_empty_position(perp_market_index)
        oracle_price_data = self.drift_client.get_oracle_price_data_for_perp_market(
            perp_market_index
        )

        free_collateral_delta = self.calculate_free_collateral_delta_for_perp(
            market, current_perp_pos, position_base_size_change, oracle_price_data.price
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
        self, market_index: int, position_base_size_change: int = 0
    ) -> int:
        current_spot_position = self.get_spot_position(market_index)
        if not current_spot_position:
            return -1

        total_collateral = self.get_total_collateral(MarginCategory.MAINTENANCE)
        maintenance_margin_requirement = self.get_margin_requirement(
            MarginCategory.MAINTENANCE, None
        )
        free_collateral = max(0, total_collateral - maintenance_margin_requirement)

        market = self.drift_client.get_spot_market_account(market_index)
        signed_token_amount = get_signed_token_amount(
            get_token_amount(
                current_spot_position.scaled_balance,
                market,
                current_spot_position.balance_type,
            ),
            current_spot_position.balance_type,
        )
        signed_token_amount += position_base_size_change

        if signed_token_amount == 0:
            return -1

        free_collateral_delta = self.calculate_free_collateral_delta_for_spot(
            market, signed_token_amount
        )

        oracle = market.oracle
        perp_market_with_same_oracle = next(
            (
                market
                for market in self.drift_client.get_perp_market_accounts()
                if market.amm.oracle == oracle
            ),
            None,
        )

        oracle_price = self.drift_client.get_oracle_price_data_for_spot_market(
            market_index
        ).price

        if perp_market_with_same_oracle:
            perp_position, _, _ = self.get_perp_position_with_lp_settle(
                perp_market_with_same_oracle.market_index, None, True
            )
            if perp_position:
                free_collateral_delta_for_perp = (
                    self.calculate_free_collateral_delta_for_perp(
                        perp_market_with_same_oracle, perp_position, 0, oracle_price
                    )
                )
                free_collateral_delta += free_collateral_delta_for_perp or 0

        if free_collateral_delta == 0:
            return -1

        liq_price_delta = (free_collateral * QUOTE_PRECISION) // free_collateral_delta
        liq_price = oracle_price - liq_price_delta

        if liq_price < 0:
            return -1

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

    def get_net_usd_value(self) -> int:
        net_spot_market_value = self.get_net_spot_market_value(None)
        unrealized_pnl = self.get_unrealized_pnl(True, None, None)
        return net_spot_market_value + unrealized_pnl

    def get_fuel_bonus(
        self, now: int, include_settled: bool = True, include_unsettled: bool = True
    ) -> dict[str, int]:
        user_account = self.get_user_account()
        total_fuel = {
            "insurance_fuel": 0,
            "taker_fuel": 0,
            "maker_fuel": 0,
            "deposit_fuel": 0,
            "borrow_fuel": 0,
            "position_fuel": 0,
        }

        if include_settled:
            user_stats = self.drift_client.get_user_stats().get_account()
            total_fuel["taker_fuel"] += user_stats.fuel_taker
            total_fuel["maker_fuel"] += user_stats.fuel_maker
            total_fuel["deposit_fuel"] += user_stats.fuel_deposits
            total_fuel["borrow_fuel"] += user_stats.fuel_borrows
            total_fuel["position_fuel"] += user_stats.fuel_positions

        if include_unsettled:
            # fuel bonus numerator is the time since the last fuel bonus update, capped at the start of the fuel program
            fuel_bonus_numerator = max(
                now - max(user_account.last_fuel_bonus_update_ts, FUEL_START_TS), 0
            )
            if fuel_bonus_numerator > 0:
                for spot_position in self.get_active_spot_positions():
                    spot_market_account = self.drift_client.get_spot_market_account(
                        spot_position.market_index
                    )
                    token_amount = self.get_token_amount(spot_position.market_index)
                    oracle_price_data = self.get_oracle_data_for_spot_market(
                        spot_position.market_index
                    )
                    twap_5min = calculate_live_oracle_twap(
                        spot_market_account.historical_oracle_data,
                        oracle_price_data,
                        now,
                        FIVE_MINUTE,
                    )
                    strict_oracle_price = StrictOraclePrice(
                        oracle_price_data.price, twap_5min
                    )
                    signed_token_value = get_strict_token_value(
                        token_amount, spot_market_account.decimals, strict_oracle_price
                    )
                    spot_fuel = calculate_spot_fuel_bonus(
                        spot_market_account, signed_token_value, fuel_bonus_numerator
                    )
                    if signed_token_value > 0:
                        total_fuel["deposit_fuel"] += spot_fuel
                    else:
                        total_fuel["borrow_fuel"] += spot_fuel

                for perp_position in self.get_active_perp_positions():
                    oracle_price_data = self.get_oracle_data_for_perp_market(
                        perp_position.market_index
                    )
                    perp_market_account = self.drift_client.get_perp_market_account(
                        perp_position.market_index
                    )
                    base_asset_value = self.get_perp_position_value(
                        perp_position.market_index, oracle_price_data, False
                    )
                    total_fuel["position_fuel"] += calculate_perp_fuel_bonus(
                        perp_market_account, base_asset_value, fuel_bonus_numerator
                    )

            user_stats = self.drift_client.get_user_stats().get_account()

            if user_stats.if_staked_gov_token_amount > 0:
                spot_market_account = self.drift_client.get_spot_market_account(
                    GOV_SPOT_MARKET_INDEX
                )
                fuel_bonus_numerator_user_stats = (
                    now - user_stats.last_fuel_if_bonus_update_ts
                )
                total_fuel["insurance_fuel"] += calculate_insurance_fuel_bonus(
                    spot_market_account,
                    user_stats.if_staked_gov_token_amount,
                    fuel_bonus_numerator_user_stats,
                )

        return total_fuel

    def get_active_spot_positions_for_user_account(
        self, user: UserAccount
    ) -> list[SpotPosition]:
        return [
            spot_position
            for spot_position in user.spot_positions
            if not is_spot_position_available(spot_position)
        ]

    def get_perp_position_value(
        self,
        market_index: int,
        oracle_price_data: OraclePriceData,
        include_open_orders: bool = False,
    ):
        perp_position = self.get_perp_position_with_lp_settle(market_index)[
            0
        ] or self.get_empty_position(market_index)

        market = self.drift_client.get_perp_market_account(perp_position.market_index)

        perp_position_value = calculate_base_asset_value_with_oracle(
            market, perp_position, oracle_price_data, include_open_orders
        )

        return perp_position_value

    def get_perp_buying_power(
        self, market_index: int, collateral_buffer: int = 0
    ) -> int:
        perp_position, _, _ = self.get_perp_position_with_lp_settle(
            market_index, None, True
        )
        perp_market = self.drift_client.get_perp_market_account(market_index)
        oracle_price_data = self.get_oracle_data_for_perp_market(market_index)
        worst_case_base_asset_amount = (
            calculate_worst_case_base_asset_amount(
                perp_position, perp_market, oracle_price_data.price
            )
            if perp_position
            else 0
        )
        free_collateral = self.get_free_collateral() - collateral_buffer
        return self.get_perp_buying_power_from_free_collateral_and_base_asset_amount(
            market_index, free_collateral, worst_case_base_asset_amount
        )

    def get_perp_buying_power_from_free_collateral_and_base_asset_amount(
        self, market_index: int, free_collateral: int, base_asset_amount: int
    ) -> int:
        margin_ratio = calculate_market_margin_ratio(
            self.drift_client.get_perp_market_account(market_index),
            base_asset_amount,
            MarginCategory.INITIAL,
            self.get_user_account().max_margin_ratio,
        )
        return (free_collateral * MARGIN_PRECISION) // margin_ratio

    def get_total_perp_position_liability(
        self,
        margin_category: Optional[MarginCategory] = None,
        liquidation_buffer: int = 0,
        include_open_orders: bool = False,
        strict: bool = False,
    ):
        total_perp_value = 0
        for perp_position in self.get_active_perp_positions():
            base_asset_value = self.calculate_weighted_perp_position_liability(
                perp_position,
                margin_category,
                liquidation_buffer,
                include_open_orders,
                strict,
            )
            total_perp_value += base_asset_value
        return total_perp_value

    def calculate_weighted_perp_position_liability(
        self,
        perp_position: PerpPosition,
        margin_category: Optional[MarginCategory] = None,
        liquidation_buffer: int = 0,
        include_open_orders: bool = False,
        strict: bool = False,
    ) -> int:
        market = self.drift_client.get_perp_market_account(perp_position.market_index)
        if not market:
            raise ValueError(
                f"No perp market account found for market {perp_position.market_index}"
            )

        if perp_position.lp_shares > 0:
            # is an lp, clone so we don't mutate the position
            perp_position, _, _ = self.get_perp_position_with_lp_settle(
                market.market_index, copy.deepcopy(perp_position), bool(margin_category)
            )

        valuation_price_data = self.drift_client.get_oracle_price_data_for_perp_market(
            market.market_index
        )
        if not valuation_price_data:
            raise ValueError(
                f"No oracle price data found for market {market.market_index}"
            )

        valuation_price = valuation_price_data.price
        if is_variant(market.status, "Settlement"):
            valuation_price = market.expiry_price

        if include_open_orders:
            worst_case = calculate_worst_case_perp_liability_value(
                perp_position, market, valuation_price
            )
            base_asset_amount = worst_case["worst_case_base_asset_amount"]
            liability_value = worst_case["worst_case_liability_value"]
        else:
            base_asset_amount = perp_position.base_asset_amount
            liability_value = calculate_perp_liability_value(
                base_asset_amount,
                valuation_price,
                is_variant(market.contract_type, "Prediction"),
            )

        if margin_category:
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
            quote_oracle_price_data = (
                self.drift_client.get_oracle_price_data_for_spot_market(
                    QUOTE_SPOT_MARKET_INDEX
                )
            )

            if strict:
                quote_price = max(
                    quote_oracle_price_data.price,
                    quote_spot_market.historical_oracle_data.last_oracle_price_twap5min,
                )
            else:
                quote_price = quote_oracle_price_data.price

            liability_value = (
                liability_value
                * quote_price
                // PRICE_PRECISION
                * margin_ratio
                // MARGIN_PRECISION
            )

            if include_open_orders:
                liability_value += (
                    perp_position.open_orders * OPEN_ORDER_MARGIN_REQUIREMENT
                )
                if perp_position.lp_shares > 0:
                    liability_value += max(
                        QUOTE_PRECISION,
                        (
                            valuation_price
                            * market.amm.order_step_size
                            * QUOTE_PRECISION
                            // AMM_RESERVE_PRECISION
                        )
                        // PRICE_PRECISION,
                    )

        return liability_value

    def get_perp_liability_value(
        self,
        market_index: int,
        oracle_price_data: OraclePriceData,
        include_open_orders: bool = False,
    ) -> int:
        user_position, _, _ = self.get_perp_position_with_lp_settle(
            market_index, None, False, True
        ) or self.get_empty_position(market_index)

        market = self.drift_client.get_perp_market_account(user_position.market_index)

        if include_open_orders:
            return calculate_worst_case_perp_liability_value(
                user_position, market, oracle_price_data.price
            )["worst_case_liability_value"]
        else:
            return calculate_perp_liability_value(
                user_position.base_asset_amount,
                oracle_price_data.price,
                is_variant(market.contract_type, "Prediction"),
            )

    def get_total_liability_value(
        self, margin_category: Optional[MarginCategory] = None
    ):
        perp_liability = self.get_total_perp_position_liability(
            margin_category, include_open_orders=True
        )

        spot_liability = self.get_spot_market_liability_value(
            margin_category=margin_category, include_open_orders=True
        )

        return perp_liability + spot_liability
