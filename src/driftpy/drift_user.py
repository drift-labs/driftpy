from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.math.positions import *
from driftpy.math.margin import *
from driftpy.math.spot_market import *
from driftpy.accounts.oracle import *
from driftpy.types import OraclePriceData


class DriftUser:
    """This class is the main way to retrieve and inspect drift user account data."""

    def __init__(
        self,
        drift_client,
        authority: Optional[Pubkey] = None,
        sub_account_id: int = 0,
        account_subscription: Optional[
            AccountSubscriptionConfig
        ] = AccountSubscriptionConfig.default(),
    ):
        """Initialize the user object

        Args:
            drift_client(DriftClient): required for program_id, idl, things (keypair doesnt matter)
            authority (Optional[Pubkey], optional): authority to investigate if None will use drift_client.authority
            sub_account_id (int, optional): subaccount of authority to investigate. Defaults to 0.
        """
        from driftpy.drift_client import DriftClient

        self.drift_client: DriftClient = drift_client
        self.authority = authority
        if self.authority is None:
            self.authority = drift_client.authority

        self.program = drift_client.program
        self.oracle_program = drift_client
        self.connection = self.program.provider.connection
        self.subaccount_id = sub_account_id

        self.user_public_key = get_user_account_public_key(
            self.program.program_id, self.authority, self.subaccount_id
        )

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

    def get_user_account(self) -> UserAccount:
        return self.account_subscriber.get_user_account_and_slot().data

    def get_token_amount(self, market_index: int) -> int:
        spot_position = self.get_spot_position(market_index)
        if spot_position is None:
            return 0

        spot_market = self.get_spot_market_account(market_index)
        return get_token_amount(
            spot_position.scaled_balance, spot_market, spot_position.balance_type
        )

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

    def get_spot_market_liability(
        self,
        market_index=None,
        margin_category=None,
        liquidation_buffer=None,
        include_open_orders=None,
    ):
        user = self.get_user_account()
        total_liability = 0
        for position in user.spot_positions:
            if is_spot_position_available(position) or (
                market_index is not None and position.market_index != market_index
            ):
                continue

            spot_market = self.drift_client.get_spot_market_account(
                position.market_index
            )

            if position.market_index == QUOTE_SPOT_MARKET_INDEX:
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

            oracle_data = self.drift_client.get_oracle_price_data(spot_market.oracle)
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

    def get_total_perp_liability(
        self,
        margin_category: Optional[MarginCategory] = None,
        liquidation_buffer: Optional[int] = 0,
        include_open_orders: bool = False,
    ):
        user = self.get_user_account()

        unrealized_pnl = 0
        for position in user.perp_positions:
            market = self.drift_client.get_perp_market_account(position.market_index)

            if position.lp_shares > 0:
                pass

            price = self.drift_client.get_oracle_price_data(market.amm.oracle).price
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
        margin_category: MarginCategory,
        liquidation_buffer: Optional[int] = 0,
        include_open_orders=True,
        include_spot=True,
    ) -> int:
        perp_liability = self.get_total_perp_liability(
            margin_category, liquidation_buffer, include_open_orders
        )

        result = perp_liability
        if include_spot:
            spot_liability = self.get_spot_market_liability(
                None, margin_category, liquidation_buffer, include_open_orders
            )
            result += spot_liability

        return result

    def get_total_collateral(
        self, margin_category: Optional[MarginCategory] = None
    ) -> int:
        spot_collateral = self.get_spot_market_asset_value(
            margin_category,
            include_open_orders=True,
        )
        pnl = self.get_unrealized_pnl(True, with_weight_margin_category=margin_category)
        total_collateral = spot_collateral + pnl
        return total_collateral

    def get_free_collateral(self):
        total_collateral = self.get_total_collateral()
        init_margin_req = self.get_margin_requirement(
            MarginCategory.INITIAL,
        )
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
        position: PerpPosition
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

    def get_spot_market_asset_value(
        self,
        margin_category: Optional[MarginCategory] = None,
        include_open_orders=True,
        market_index: Optional[int] = None,
    ):
        user = self.get_user_account()
        total_value = 0
        for position in user.spot_positions:
            if is_spot_position_available(position) or (
                market_index is not None and position.market_index != market_index
            ):
                continue

            spot_market = self.drift_client.get_spot_market_account(
                position.market_index
            )

            if position.market_index == QUOTE_SPOT_MARKET_INDEX:
                spot_token_value = get_token_amount(
                    position.scaled_balance, spot_market, position.balance_type
                )

                match str(position.balance_type):
                    case "SpotBalanceType.Deposit()":
                        spot_token_value *= 1
                    case "SpotBalanceType.Borrow()":
                        spot_token_value *= -1
                    case _:
                        raise Exception(
                            f"Invalid balance type: {position.balance_type}"
                        )

                total_value += spot_token_value
                continue

            oracle_data = self.drift_client.get_oracle_price_data(spot_market.oracle)

            if not include_open_orders:
                token_amount = get_token_amount(
                    position.scaled_balance, spot_market, position.balance_type
                )
                spot_token_value = get_spot_asset_value(
                    token_amount, oracle_data, spot_market, margin_category
                )
                match str(position.balance_type):
                    case "SpotBalanceType.Deposit()":
                        spot_token_value *= 1
                    case "SpotBalanceType.Borrow()":
                        spot_token_value *= -1
                    case _:
                        raise Exception(
                            f"Invalid balance type: {position.balance_type}"
                        )
                total_value += spot_token_value
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

    def get_leverage(self, margin_category: Optional[MarginCategory] = None) -> int:
        total_liability = self.get_margin_requirement(margin_category, None)
        total_asset_value = self.get_total_collateral(margin_category)

        if total_asset_value == 0 or total_liability == 0:
            return 0

        leverage = total_liability * 10_000 / total_asset_value

        return leverage

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
