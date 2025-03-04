import copy
from typing import Callable, Dict, Generator, List, Optional, Tuple, Union

from solders.pubkey import Pubkey

from driftpy.constants.numeric_constants import (
    BASE_PRECISION,
    PRICE_PRECISION,
    QUOTE_PRECISION,
)
from driftpy.dlob.dlob_helpers import get_maker_rebate, get_node_lists
from driftpy.dlob.dlob_node import (
    DLOBNode,
    FloatingLimitOrderNode,
    MarketOrderNode,
    RestingLimitOrderNode,
    TakingLimitOrderNode,
    TriggerOrderNode,
    VAMMNode,
)
from driftpy.dlob.node_list import NodeList, get_vamm_node_generator
from driftpy.dlob.orderbook_levels import (
    L2OrderBook,
    L2OrderBookGenerator,
    L3Level,
    L3OrderBook,
    create_l2_levels,
    get_l2_generator_from_dlob_nodes,
    merge_l2_level_generators,
)
from driftpy.math.auction import is_fallback_available_liquidity_source
from driftpy.math.exchange_status import amm_paused, exchange_paused, fill_paused
from driftpy.math.orders import (
    get_limit_price,
    is_order_expired,
    is_resting_limit_order,
    is_taking_order,
    is_triggered,
    must_be_triggered,
)
from driftpy.types import (
    MarketType,
    OraclePriceData,
    Order,
    OrderRecord,
    PerpMarketAccount,
    PositionDirection,
    SpotMarketAccount,
    StateAccount,
    UserAccount,
    is_one_of_variant,
    is_variant,
    market_type_to_string,
)


class MarketNodeLists:
    def __init__(self):
        self.resting_limit = {
            "ask": NodeList[RestingLimitOrderNode]("restingLimit", "asc"),
            "bid": NodeList[RestingLimitOrderNode]("restingLimit", "desc"),
        }
        self.floating_limit = {
            "ask": NodeList[FloatingLimitOrderNode]("floatingLimit", "asc"),
            "bid": NodeList[FloatingLimitOrderNode]("floatingLimit", "desc"),
        }
        self.taking_limit = {
            "ask": NodeList[TakingLimitOrderNode]("takingLimit", "asc"),
            "bid": NodeList[TakingLimitOrderNode](
                "takingLimit", "asc"
            ),  # always sort ascending for market orders
        }
        self.market = {
            "ask": NodeList[MarketOrderNode]("market", "asc"),
            "bid": NodeList[MarketOrderNode](
                "market", "asc"
            ),  # always sort ascending for market orders
        }
        self.trigger = {
            "above": NodeList[TriggerOrderNode]("trigger", "asc"),
            "below": NodeList[TriggerOrderNode]("trigger", "desc"),
        }


OrderBookCallback = Callable[[], None]
"""
    Receives a DLOBNode and is expected to return True if the node should
    be taken into account when generating, or False otherwise

    Currentl used in get_resting_limit_bids and get_resting_limit_asks
"""
DLOBFilterFcn = Callable[[DLOBNode], bool]


class NodeToFill:
    def __init__(self, node: DLOBNode, maker_nodes: List[DLOBNode]):
        self.node = node
        self.maker = maker_nodes


class NodeToTrigger:
    def __init__(self, node: TriggerOrderNode):
        self.node = node


SUPPORTED_ORDER_TYPES = [
    "Market",
    "Limit",
    "TriggerMarket",
    "TriggerLimit",
    "Oracle",
]


class DLOB:
    def __init__(self):
        self.open_orders: Dict[str, set] = {}
        self.order_lists: Dict[str, Dict[int, MarketNodeLists]] = {}
        self.max_slot_for_resting_limit_orders = 0
        self.initialized = False
        self.init()

    def init(self):
        self.open_orders["perp"] = set()
        self.open_orders["spot"] = set()
        self.order_lists["perp"] = {}
        self.order_lists["spot"] = {}

    def init_from_usermap(self, usermap, slot: int) -> bool:
        if self.initialized:
            return False

        for user in usermap.values():
            user_account: UserAccount = user.get_user_account()
            user_account_pubkey = user.user_public_key

            for order in user_account.orders:
                self.insert_order(order, user_account_pubkey, slot)

        self.initialized = True
        return True

    def add_order_list(self, market_type: str, market_index: int) -> None:
        if market_type not in self.order_lists:
            self.order_lists[market_type] = {}

        self.order_lists[market_type][market_index] = MarketNodeLists()

    def get_list_for_order(self, order: Order, slot: int) -> Optional[NodeList]:
        is_inactive_trigger_order = must_be_triggered(order) and not is_triggered(order)

        if is_inactive_trigger_order:
            node_type = "trigger"
        elif is_one_of_variant(order.order_type, ["Market", "TriggerMarket", "Oracle"]):
            node_type = "market"
        elif order.oracle_price_offset != 0:
            node_type = "floating_limit"
        else:
            is_resting = is_resting_limit_order(order, slot)
            node_type = "resting_limit" if is_resting else "taking_limit"

        if is_inactive_trigger_order:
            sub_type = (
                "above" if is_variant(order.trigger_condition, "Above") else "below"
            )
        else:
            sub_type = "bid" if is_variant(order.direction, "Long") else "ask"

        market_type = market_type_to_string(order.market_type)

        if market_type not in self.order_lists:
            return None

        market_node_lists = self.order_lists[market_type][order.market_index]

        if hasattr(market_node_lists, node_type):
            node_list_group = getattr(market_node_lists, node_type)
            if sub_type in node_list_group:
                return node_list_group[sub_type]

        return None

    def insert_order(
        self,
        order: Order,
        user_account: Pubkey,
        slot: int,
        on_insert: Optional[OrderBookCallback] = None,
    ):
        from driftpy.dlob.node_list import get_order_signature

        if not is_variant(order.status, "Open"):
            return

        if not is_one_of_variant(order.order_type, SUPPORTED_ORDER_TYPES):
            return

        market_type = market_type_to_string(order.market_type)

        if order.market_index not in self.order_lists.get(market_type):
            self.add_order_list(market_type, order.market_index)

        if is_variant(order.status, "Open"):
            self.open_orders.get(market_type).add(
                get_order_signature(order.order_id, user_account)
            )

        self.get_list_for_order(order, slot).insert(order, market_type, user_account)

        if on_insert is not None and callable(on_insert):
            on_insert()

    def get_order(self, order_id: int, user_account: Pubkey) -> Optional[Order]:
        from driftpy.dlob.node_list import get_order_signature

        order_signature = get_order_signature(order_id, user_account)
        for node_list in get_node_lists(self.order_lists):
            node = node_list.get(order_signature)
            if node:
                return node.order

        return None

    def _update_resting_limit_orders_for_market_type(
        self, slot: int, market_type_str: str
    ):
        if market_type_str not in self.order_lists:
            return

        for _, node_lists in self.order_lists[market_type_str].items():
            nodes_to_update = []

            for node in node_lists.taking_limit["ask"].get_generator():
                if not is_resting_limit_order(node.order, slot):
                    continue
                nodes_to_update.append({"side": "ask", "node": node})

            for node in node_lists.taking_limit["bid"].get_generator():
                if not is_resting_limit_order(node.order, slot):
                    continue
                nodes_to_update.append({"side": "bid", "node": node})

            for node_to_update in nodes_to_update:
                side = node_to_update["side"]
                node = node_to_update["node"]
                node_lists.taking_limit[side].remove(node.order, node.user_account)
                node_lists.resting_limit[side].insert(
                    node.order, market_type_str, node.user_account
                )

    def update_resting_limit_orders(self, slot: int):
        if slot <= self.max_slot_for_resting_limit_orders:
            return

        self.max_slot_for_resting_limit_orders = slot

        self._update_resting_limit_orders_for_market_type(slot, "perp")
        self._update_resting_limit_orders_for_market_type(slot, "spot")

    def update_order(
        self,
        order: Order,
        user_account: Pubkey,
        slot: int,
        cumulative_base_asset_amount_filled: int,
        on_update: Optional[OrderBookCallback] = None,
    ):
        self.update_resting_limit_orders(slot)

        if order.base_asset_amount == cumulative_base_asset_amount_filled:
            self.delete(order, user_account, slot)
            return

        if order.base_asset_amount_filled == cumulative_base_asset_amount_filled:
            return

        new_order = copy.deepcopy(order)

        new_order.base_asset_amount_filled = cumulative_base_asset_amount_filled

        self.get_list_for_order(order, slot).update(new_order, user_account)

        if on_update is not None and callable(on_update):
            on_update()

    def delete(
        self,
        order: Order,
        user_account: Pubkey,
        slot: int,
        on_delete: Optional[OrderBookCallback] = None,
    ):
        if not is_variant(order.status, "Open"):
            return

        self.update_resting_limit_orders(slot)

        self.get_list_for_order(order, slot).remove(order, user_account)

        if on_delete is not None and callable(on_delete):
            on_delete()

    def clear(self):
        for market_type in self.open_orders.keys():
            self.open_orders.get(market_type).clear()

        self.open_orders.clear()

        for market_type in self.order_lists.keys():
            for market_index in self.order_lists.get(market_type).keys():
                node_lists: MarketNodeLists = self.order_lists.get(market_type).get(
                    market_index
                )

                for side in vars(node_lists).keys():
                    for order_type in getattr(node_lists, side, {}).keys():
                        getattr(node_lists, side)[order_type].clear()

        self.order_lists.clear()

        self.max_slot_for_resting_limit_orders = 0

        self.init()

    def trigger(
        self,
        order: Order,
        user_account: Pubkey,
        slot: int,
        on_trigger: Optional[OrderBookCallback] = None,
    ):
        if is_variant(order, "Init"):
            return

        self.update_resting_limit_orders(slot)

        if is_triggered(order):
            return

        market_type = market_type_to_string(order.market_type)

        trigger_list = (
            self.order_lists.get(market_type)
            .get(order.market_index)
            .trigger[
                "above" if is_variant(order.trigger_condition, "Above") else "Below"
            ]
        )
        trigger_list.remove(order, user_account)

        self.get_list_for_order(order, slot).insert(order, market_type, user_account)

        if on_trigger is not None and callable(on_trigger):
            on_trigger()

    def handle_order_record(self, record: OrderRecord, slot: int):
        self.insert_order(record.order, record.user, slot)

    def _get_best_node(
        self,
        generator_list: List[Generator[DLOBNode, None, None]],
        oracle_price_data: OraclePriceData,
        slot: int,
        compare_fcn: Callable[[DLOBNode, DLOBNode, int, OraclePriceData], bool],
        filter_fcn: Optional[DLOBFilterFcn] = None,
    ) -> Generator[DLOBNode, None, None]:
        generators = [
            {"next": next(generator, None), "generator": generator}
            for generator in generator_list
        ]

        side_exhausted = False
        while not side_exhausted:
            best_generator = None
            for current_generator in generators:
                if current_generator["next"] is None:
                    continue
                if best_generator is None or compare_fcn(
                    best_generator["next"],
                    current_generator["next"],
                    slot,
                    oracle_price_data,
                ):
                    best_generator = current_generator

            if best_generator and best_generator["next"]:
                # Skip this node is it's already completely filled or fails filter function
                if best_generator["next"].is_base_filled() or (
                    filter_fcn and not filter_fcn(best_generator["next"])
                ):
                    best_generator["next"] = next(best_generator["generator"], None)
                    continue

                yield best_generator["next"]
                try:
                    best_generator["next"] = next(best_generator["generator"])
                except StopIteration:
                    best_generator["next"] = None
            else:
                side_exhausted = True

    def estimate_fill_with_exact_base_amount(
        self,
        market_index: int,
        market_type: MarketType,
        base_amount: int,
        order_direction: PositionDirection,
        slot: int,
        oracle_price_data: OraclePriceData,
    ) -> int:
        if is_variant(order_direction, "Long"):
            return self._estimate_fill_exact_base_amount_in_for_side(
                base_amount,
                oracle_price_data,
                slot,
                self.get_resting_limit_asks(
                    market_index, slot, market_type, oracle_price_data
                ),
            )
        elif is_variant(order_direction, "Short"):
            return self._estimate_fill_exact_base_amount_in_for_side(
                base_amount,
                oracle_price_data,
                slot,
                self.get_resting_limit_bids(
                    market_index, slot, market_type, oracle_price_data
                ),
            )
        return 0

    def _estimate_fill_exact_base_amount_in_for_side(
        self,
        base_amount_in: int,
        oracle_price_data: OraclePriceData,
        slot: int,
        dlob_side: Generator[DLOBNode, None, None],
    ) -> int:
        running_sum_quote = 0
        running_sum_base = 0
        for side in dlob_side:
            price = side.get_price(oracle_price_data, slot)

            base_amount_remaining = (
                side.order.base_asset_amount - side.order.base_asset_amount_filled
            )

            if running_sum_base + base_amount_remaining > base_amount_in:
                remaining_base = base_amount_in - running_sum_base
                running_sum_base += remaining_base
                running_sum_quote += remaining_base * price
                break
            else:
                running_sum_base += base_amount_remaining
                running_sum_quote += base_amount_remaining * price

        return running_sum_quote * QUOTE_PRECISION // (BASE_PRECISION * PRICE_PRECISION)

    def get_resting_limit_asks(
        self,
        market_index: int,
        slot: int,
        market_type: MarketType,
        oracle_price_data: OraclePriceData,
        filter_fcn: Optional[DLOBFilterFcn] = None,
    ) -> Generator[DLOBNode, None, None]:
        if is_variant(market_type, "Spot") and not oracle_price_data:
            raise ValueError("Must provide oracle price data to get spot asks")

        self.update_resting_limit_orders(slot)

        market_type_str = market_type_to_string(market_type)
        node_lists = self.order_lists.get(market_type_str, {}).get(market_index)

        if node_lists is None:
            return

        generator_list = [
            node_lists.resting_limit["ask"].get_generator(),
            node_lists.floating_limit["ask"].get_generator(),
        ]

        def cmp(best_node, current_node, slot, oracle_price_data):
            return best_node.get_price(
                oracle_price_data, slot
            ) < current_node.get_price(oracle_price_data, slot)

        yield from self._get_best_node(
            generator_list, oracle_price_data, slot, cmp, filter_fcn
        )

    def get_resting_limit_bids(
        self,
        market_index: int,
        slot: int,
        market_type: MarketType,
        oracle_price_data: OraclePriceData,
        filter_fcn: Optional[DLOBFilterFcn] = None,
    ) -> Generator[DLOBNode, None, None]:
        if is_variant(market_type, "Spot") and not oracle_price_data:
            raise ValueError("Must provide oracle price data to get spot bids")

        self.update_resting_limit_orders(slot)

        market_type_str = market_type_to_string(market_type)
        node_lists = self.order_lists.get(market_type_str, {}).get(market_index)

        if node_lists is None:
            return

        generator_list = [
            node_lists.resting_limit["bid"].get_generator(),
            node_lists.floating_limit["bid"].get_generator(),
        ]

        def cmp(best_node, current_node, slot, oracle_price_data):
            return best_node.get_price(
                oracle_price_data, slot
            ) > current_node.get_price(oracle_price_data, slot)

        yield from self._get_best_node(
            generator_list, oracle_price_data, slot, cmp, filter_fcn
        )

    def get_best_ask(
        self,
        market_index: int,
        slot: int,
        market_type: MarketType,
        oracle_price_data: OraclePriceData,
    ) -> int:
        return next(
            self.get_resting_limit_asks(
                market_index, slot, market_type, oracle_price_data
            )
        ).get_price(oracle_price_data, slot)

    def get_best_bid(
        self,
        market_index: int,
        slot: int,
        market_type: MarketType,
        oracle_price_data: OraclePriceData,
    ) -> int:
        return next(
            self.get_resting_limit_bids(
                market_index, slot, market_type, oracle_price_data
            )
        ).get_price(oracle_price_data, slot)

    def get_taking_bids(
        self,
        market_index: int,
        market_type: MarketType,
        slot: int,
        oracle_price_data: OraclePriceData,
    ) -> Generator[DLOBNode, None, None]:
        market_type_str = market_type_to_string(market_type)
        order_lists = self.order_lists.get(market_type_str, {}).get(market_index)

        if order_lists is None:
            return

        self.update_resting_limit_orders(slot)

        generator_list = [
            order_lists.market["bid"].get_generator(),
            order_lists.taking_limit["bid"].get_generator(),
        ]

        def cmp(best_node, current_node, slot, oracle_price_data):
            return best_node.order.slot > current_node.order.slot

        yield from self._get_best_node(
            generator_list,
            oracle_price_data,
            slot,
            cmp,
        )

    def get_taking_asks(
        self,
        market_index: int,
        market_type: MarketType,
        slot: int,
        oracle_price_data: OraclePriceData,
    ) -> Generator[DLOBNode, None, None]:
        market_type_str = market_type_to_string(market_type)
        order_lists = self.order_lists.get(market_type_str, {}).get(market_index)

        if order_lists is None:
            return

        self.update_resting_limit_orders(slot)

        generator_list = [
            order_lists.market["ask"].get_generator(),
            order_lists.taking_limit["ask"].get_generator(),
        ]

        def cmp(best_node, current_node, slot, oracle_price_data):
            return best_node.order.slot > current_node.order.slot

        yield from self._get_best_node(generator_list, oracle_price_data, slot, cmp)

    def get_asks(
        self,
        market_index: int,
        slot: int,
        market_type: MarketType,
        oracle_price_data: OraclePriceData,
        fallback_ask: Optional[int] = None,
    ) -> Generator[DLOBNode, None, None]:
        if is_variant(market_type, "Spot") and not oracle_price_data:
            raise ValueError("Must provide oracle price data to get spot asks")

        generator_list = [
            self.get_taking_asks(market_index, market_type, slot, oracle_price_data),
            self.get_resting_limit_asks(
                market_index, slot, market_type, oracle_price_data
            ),
        ]

        market_type_str = market_type_to_string(market_type)
        if market_type_str == "perp" and fallback_ask:
            generator_list.append(get_vamm_node_generator(fallback_ask))

        def cmp(best_node, current_node, slot, oracle_price_data):
            best_node_taking = bool(best_node.order) and is_taking_order(
                best_node.order, slot
            )
            current_node_taking = bool(current_node.order) and is_taking_order(
                current_node.order, slot
            )

            if best_node_taking and current_node_taking:
                return best_node.order.slot < current_node.order.slot

            if best_node_taking:
                return True

            if current_node_taking:
                return False

            return best_node.get_price(
                oracle_price_data, slot
            ) < current_node.get_price(oracle_price_data, slot)

        return self._get_best_node(generator_list, oracle_price_data, slot, cmp)

    def get_bids(
        self,
        market_index: int,
        slot: int,
        market_type: int,
        oracle_price_data: OraclePriceData,
        fallback_bid: Optional[int] = None,
    ) -> Generator[DLOBNode, None, None]:
        if is_variant(market_type, "Spot") and not oracle_price_data:
            raise ValueError("must provide oracle price data to get spot bids")

        generator_list = []

        generator_list.append(
            self.get_taking_bids(market_index, market_type, slot, oracle_price_data)
        )

        market_type_str = market_type_to_string(market_type)
        if market_type_str == "perp" and fallback_bid:
            generator_list.append(get_vamm_node_generator(fallback_bid))

        generator_list.append(
            self.get_resting_limit_bids(
                market_index, slot, market_type, oracle_price_data
            )
        )

        def cmp(best_node, current_node, slot, oracle_price_data):
            if isinstance(best_node, RestingLimitOrderNode) or isinstance(
                current_node, RestingLimitOrderNode
            ):
                return isinstance(best_node, RestingLimitOrderNode)

            if isinstance(best_node, VAMMNode) or isinstance(current_node, VAMMNode):
                return isinstance(best_node, VAMMNode)

            return best_node.get_price(
                oracle_price_data, slot
            ) < current_node.get_price(oracle_price_data, slot)

        return self._get_best_node(generator_list, oracle_price_data, slot, cmp)

    def find_nodes_crossing_fallback_liquidity(
        self,
        market_type: MarketType,
        slot: int,
        oracle_price_data: OraclePriceData,
        node_generator: Generator[DLOBNode, None, None],
        does_cross: Callable[[Optional[int]], bool],
        min_auction_duration: int,
    ) -> List[NodeToFill]:
        nodes_to_fill = []

        for node in node_generator:
            if is_variant(market_type, "Spot") and node.order.post_only:
                continue

            node_price = get_limit_price(node.order, oracle_price_data, slot)

            crosses = does_cross(node_price)

            fallback_available = is_variant(
                market_type, "Spot"
            ) or is_fallback_available_liquidity_source(
                node.order, min_auction_duration, slot
            )

            if crosses and fallback_available:
                nodes_to_fill.append(NodeToFill(node, []))

        return nodes_to_fill

    def find_taking_nodes_crossing_maker_nodes(
        self,
        market_index: int,
        slot: int,
        market_type: MarketType,
        oracle_price_data: OraclePriceData,
        taker_node_generator: Generator[DLOBNode, None, None],
        maker_node_generator_fn: Callable[
            [int, int, MarketType, OraclePriceData], Generator[DLOBNode, None, None]
        ],
        does_cross: Callable[[int, int], bool],
    ) -> List[NodeToFill]:
        nodes_to_fill: List[NodeToFill] = []

        for taker_node in taker_node_generator:
            maker_node_generator = maker_node_generator_fn(
                market_index, slot, market_type, oracle_price_data
            )

            for maker_node in maker_node_generator:
                # Check if nodes are from the same user
                if taker_node.user_account == maker_node.user_account:
                    continue

                maker_price = maker_node.get_price(oracle_price_data, slot)
                taker_price = taker_node.get_price(oracle_price_data, slot)

                if not does_cross(taker_price, maker_price):
                    break

                nodes_to_fill.append(NodeToFill(taker_node, [maker_node]))

                # Update orders
                maker_base_remaining = (
                    maker_node.order.base_asset_amount
                    - maker_node.order.base_asset_amount_filled
                )
                taker_base_remaining = (
                    taker_node.order.base_asset_amount
                    - taker_node.order.base_asset_amount_filled
                )

                base_filled = min(maker_base_remaining, taker_base_remaining)

                new_maker_order = copy.deepcopy(maker_node.order)
                new_maker_order.base_asset_amount_filled += base_filled

                self.get_list_for_order(new_maker_order, slot).update(
                    new_maker_order, maker_node.user_account
                )

                new_taker_order = copy.deepcopy(taker_node.order)
                new_taker_order.base_asset_amount_filled += base_filled

                self.get_list_for_order(new_taker_order, slot).update(
                    new_taker_order, taker_node.user_account
                )

                if (
                    new_taker_order.base_asset_amount_filled
                    == taker_node.order.base_asset_amount
                ):
                    break

        return nodes_to_fill

    def find_jit_auction_nodes_to_fill(
        self,
        market_index: int,
        slot: int,
        oracle_price_data: OraclePriceData,
        market_type: MarketType,
    ) -> List[NodeToFill]:
        nodes_to_fill: List[NodeToFill] = []

        for market_bid in self.get_taking_bids(
            market_index, market_type, slot, oracle_price_data
        ):
            nodes_to_fill.append(NodeToFill(market_bid, []))

        for market_ask in self.get_taking_asks(
            market_index, market_type, slot, oracle_price_data
        ):
            nodes_to_fill.append(NodeToFill(market_ask, []))

        return nodes_to_fill

    def find_taking_nodes_to_fill(
        self,
        market_index: int,
        slot: int,
        market_type: MarketType,
        oracle_price_data: OraclePriceData,
        is_amm_paused: bool,
        min_auction_duration: int,
        fallback_ask: Optional[int] = None,
        fallback_bid: Optional[int] = None,
    ) -> List[NodeToFill]:
        """
        THIS NEEDS UNIT TESTS BEFORE BEING USED IN PROD
        """
        nodes_to_fill: List[NodeToFill] = []

        # Process taking asks
        taking_order_generator = self.get_taking_asks(
            market_index, market_type, slot, oracle_price_data
        )
        maker_node_generator_fn = self.get_resting_limit_bids

        does_cross = lambda taker_price, maker_price: (
            (taker_price is None or taker_price <= maker_price)
            if (
                not is_variant(market_type, "Spot")
                or (fallback_bid and maker_price < fallback_bid)
            )
            else False
        )
        taking_asks_crossing_bids = self.find_taking_nodes_crossing_maker_nodes(
            market_index,
            slot,
            market_type,
            oracle_price_data,
            taking_order_generator,
            maker_node_generator_fn,
            does_cross,
        )
        nodes_to_fill.extend(taking_asks_crossing_bids)

        # Process fallback asks
        if fallback_bid is not None and not is_amm_paused:
            taking_order_generator = self.get_taking_asks(
                market_index, market_type, slot, oracle_price_data
            )

            def does_cross(price: Optional[int] = None) -> bool:
                return price is None or price <= fallback_ask

            taking_asks_crossing_fallback = self.find_nodes_crossing_fallback_liquidity(
                market_type,
                slot,
                oracle_price_data,
                taking_order_generator,
                does_cross,
                min_auction_duration,
            )
            nodes_to_fill.extend(taking_asks_crossing_fallback)

        # Process taking bids
        taking_order_generator = self.get_taking_bids(
            market_index, market_type, slot, oracle_price_data
        )
        maker_node_generator_fn = self.get_resting_limit_asks

        does_cross = lambda taker_price, maker_price: (
            (taker_price is None or taker_price >= maker_price)
            if (
                not is_variant(market_type, "Spot")
                or (fallback_bid and maker_price > fallback_bid)
            )
            else False
        )
        taking_bids_to_fill = self.find_taking_nodes_crossing_maker_nodes(
            market_index,
            slot,
            market_type,
            oracle_price_data,
            taking_order_generator,
            maker_node_generator_fn,
            does_cross,
        )
        nodes_to_fill.extend(taking_bids_to_fill)

        # Process fallback bids
        if fallback_ask is not None and not is_amm_paused:
            taking_order_generator = self.get_taking_bids(
                market_index, market_type, slot, oracle_price_data
            )

            def does_cross(price: Optional[int] = None) -> bool:
                return price is None or price >= fallback_ask

            taking_bids_crossing_fallback = self.find_nodes_crossing_fallback_liquidity(
                market_type,
                slot,
                oracle_price_data,
                taking_order_generator,
                does_cross,
                min_auction_duration,
            )
            nodes_to_fill.extend(taking_bids_crossing_fallback)

        return nodes_to_fill

    def determine_maker_and_taker(
        self, ask: DLOBNode, bid: DLOBNode
    ) -> Union[Tuple[DLOBNode, DLOBNode], None]:
        ask_slot = ask.order.slot + ask.order.auction_duration
        bid_slot = bid.order.slot + bid.order.auction_duration

        if bid.order.post_only and ask.order.post_only:
            return None
        elif bid.order.post_only:
            return (ask, bid)
        elif ask.order.post_only:
            return (bid, ask)
        elif ask_slot <= bid_slot:
            return (bid, ask)
        else:
            return (ask, bid)

    def find_crossing_resting_limit_orders(
        self,
        market_index: int,
        slot: int,
        market_type: MarketType,
        oracle_price_data: OraclePriceData,
    ) -> List[NodeToFill]:
        nodes_to_fill: List[NodeToFill] = []

        for ask in self.get_resting_limit_asks(
            market_index, slot, market_type, oracle_price_data
        ):
            bid_generator = self.get_resting_limit_bids(
                market_index, slot, market_type, oracle_price_data
            )

            for bid in bid_generator:
                bid_price = bid.get_price(oracle_price_data, slot)
                ask_price = ask.get_price(oracle_price_data, slot)

                # don't cross
                if bid_price < ask_price:
                    break

                bid_order = bid.order
                ask_order = ask.order

                # can't match from same user
                if bid.user_account == ask.user_account:
                    break

                maker_and_taker = self.determine_maker_and_taker(ask, bid)

                # unable to match maker and taker due to post only or slot
                if not maker_and_taker:
                    continue

                taker, maker = maker_and_taker

                bid_base_remaining = (
                    bid_order.base_asset_amount - bid_order.base_asset_amount_filled
                )
                ask_base_remaining = (
                    ask_order.base_asset_amount - ask_order.base_asset_amount_filled
                )

                base_filled = min(bid_base_remaining, ask_base_remaining)

                new_bid = copy.deepcopy(bid_order)
                new_bid.base_asset_amount_filled += base_filled
                self.get_list_for_order(new_bid, slot).update(new_bid, bid.user_account)

                new_ask = copy.deepcopy(ask_order)
                new_ask.base_asset_amount_filled += base_filled
                self.get_list_for_order(new_ask, slot).update(new_ask, ask.user_account)

                nodes_to_fill.append(NodeToFill(taker, [maker]))

                if new_ask.base_asset_amount == new_ask.base_asset_amount_filled:
                    break

        return nodes_to_fill

    def find_resting_limit_order_nodes_to_fill(
        self,
        market_index: int,
        slot: int,
        market_type: MarketType,
        oracle_price_data: OraclePriceData,
        is_amm_paused: bool,
        min_auction_duration: int,
        maker_rebate_numerator: int,
        maker_rebate_denominator: int,
        fallback_ask: Optional[int] = None,
        fallback_bid: Optional[int] = None,
    ) -> List[NodeToFill]:
        nodes_to_fill: List[NodeToFill] = []

        crossing_nodes = self.find_crossing_resting_limit_orders(
            market_index, slot, market_type, oracle_price_data
        )

        for crossing_node in crossing_nodes:
            nodes_to_fill.append(crossing_node)

        if fallback_bid is not None and not is_amm_paused:
            ask_generator = self.get_resting_limit_asks(
                market_index, slot, market_type, oracle_price_data
            )

            fallback_bid_with_buffer = fallback_bid - (
                fallback_bid * maker_rebate_numerator // maker_rebate_denominator
            )

            asks_crossing_fallback = self.find_nodes_crossing_fallback_liquidity(
                market_type,
                slot,
                oracle_price_data,
                ask_generator,
                lambda ask_price: ask_price <= fallback_bid_with_buffer,
                min_auction_duration,
            )

            for ask_crossing_fallback in asks_crossing_fallback:
                nodes_to_fill.append(ask_crossing_fallback)

        if fallback_ask is not None and not is_amm_paused:
            bid_generator = self.get_resting_limit_bids(
                market_index, slot, market_type, oracle_price_data
            )

            fallback_ask_with_buffer = fallback_ask + (
                fallback_ask * maker_rebate_numerator // maker_rebate_denominator
            )

            bids_crossing_fallback = self.find_nodes_crossing_fallback_liquidity(
                market_type,
                slot,
                oracle_price_data,
                bid_generator,
                lambda bid_price: bid_price >= fallback_ask_with_buffer,
                min_auction_duration,
            )

            for bid_crossing_fallback in bids_crossing_fallback:
                nodes_to_fill.append(bid_crossing_fallback)

        return nodes_to_fill

    def find_expired_nodes_to_fill(
        self, market_index: int, ts: int, market_type: MarketType
    ) -> List[NodeToFill]:
        nodes_to_fill: List[NodeToFill] = []

        market_type_str = market_type_to_string(market_type)
        node_lists = self.order_lists.get(market_type_str, {}).get(market_index)

        if node_lists is None:
            return nodes_to_fill

        bid_generators = [
            node_lists.taking_limit["bid"].get_generator(),
            node_lists.resting_limit["bid"].get_generator(),
            node_lists.floating_limit["bid"].get_generator(),
            node_lists.market["bid"].get_generator(),
        ]
        ask_generators = [
            node_lists.taking_limit["ask"].get_generator(),
            node_lists.resting_limit["ask"].get_generator(),
            node_lists.floating_limit["ask"].get_generator(),
            node_lists.market["ask"].get_generator(),
        ]

        for bid_generator in bid_generators:
            for bid in bid_generator:
                if is_order_expired(bid.order, ts, True):
                    nodes_to_fill.append(NodeToFill(bid, []))

        for ask_generator in ask_generators:
            for ask in ask_generator:
                if is_order_expired(ask.order, ts, True):
                    nodes_to_fill.append(NodeToFill(ask, []))

        return nodes_to_fill

    def merge_nodes_to_fill(
        self,
        resting_limit_order_nodes_to_fill: List[NodeToFill],
        taking_order_nodes_to_fill: List[NodeToFill],
    ) -> List[NodeToFill]:
        from driftpy.dlob.node_list import get_order_signature

        nodes_to_fill: List[NodeToFill] = []
        merged_nodes_to_fill: Dict[str, NodeToFill] = {}

        def merge_nodes_to_fill_helper(nodes_to_fill_list):
            for node_to_fill in nodes_to_fill_list:
                node_signature = get_order_signature(
                    node_to_fill.node.order.order_id, node_to_fill.node.user_account
                )

                if node_signature not in merged_nodes_to_fill:
                    merged_nodes_to_fill[node_signature] = NodeToFill(
                        node_to_fill.node, []
                    )

                if node_to_fill.maker is not None:
                    merged_nodes_to_fill[node_signature].maker.extend(
                        node_to_fill.maker
                    )

        merge_nodes_to_fill_helper(resting_limit_order_nodes_to_fill)
        merge_nodes_to_fill_helper(taking_order_nodes_to_fill)

        values = merged_nodes_to_fill.values()

        for value in values:
            nodes_to_fill.append(value)

        return nodes_to_fill

    def find_nodes_to_fill(
        self,
        market_index: int,
        slot: int,
        ts: int,
        market_type: MarketType,
        oracle_price_data: OraclePriceData,
        state_account: StateAccount,
        market_account: Union[PerpMarketAccount, SpotMarketAccount],
        fallback_bid: Optional[int] = None,
        fallback_ask: Optional[int] = None,
    ) -> List[NodeToFill]:
        if fill_paused(state_account, market_account):
            return []

        is_amm_paused = amm_paused(state_account, market_account)

        min_auction_duration = (
            state_account.min_perp_auction_duration
            if is_variant(market_type, "Perp")
            else 0
        )

        maker_rebate_numerator, maker_rebate_denominator = get_maker_rebate(
            market_type, state_account, market_account
        )

        resting_limit_order_nodes_to_fill = self.find_resting_limit_order_nodes_to_fill(
            market_index,
            slot,
            market_type,
            oracle_price_data,
            is_amm_paused,
            min_auction_duration,
            maker_rebate_numerator,
            maker_rebate_denominator,
            fallback_ask,
            fallback_bid,
        )

        taking_order_nodes_to_fill = self.find_taking_nodes_to_fill(
            market_index,
            slot,
            market_type,
            oracle_price_data,
            is_amm_paused,
            min_auction_duration,
            fallback_ask,
            fallback_bid,
        )

        expired_nodes_to_fill = self.find_expired_nodes_to_fill(
            market_index, ts, market_type
        )

        # for spot, multiple makers isn't supported, so don't fill
        if is_variant(market_type, "Spot"):
            return (
                resting_limit_order_nodes_to_fill
                + taking_order_nodes_to_fill
                + expired_nodes_to_fill
            )

        return (
            self.merge_nodes_to_fill(
                resting_limit_order_nodes_to_fill, taking_order_nodes_to_fill
            )
            + expired_nodes_to_fill
        )

    def find_nodes_to_trigger(
        self,
        market_index: int,
        oracle_price: int,
        market_type: MarketType,
        state_account: StateAccount,
    ) -> list[NodeToTrigger]:
        if exchange_paused(state_account):
            return []

        nodes_to_trigger = []
        market_type_str = market_type_to_string(market_type)
        market_node_lists = self.order_lists.get(market_type_str).get(market_index)  # type: ignore

        trigger_above_list = market_node_lists.trigger["above"] or None  # type: ignore

        if trigger_above_list:
            for node in trigger_above_list.get_generator():
                if oracle_price > node.order.trigger_price:
                    nodes_to_trigger.append(NodeToTrigger(node))
                else:
                    break

        trigger_below_list = market_node_lists.trigger["below"] or None  # type: ignore

        if trigger_below_list:
            for node in trigger_below_list.get_generator():
                if oracle_price < node.order.trigger_price:
                    nodes_to_trigger.append(NodeToTrigger(node))
                else:
                    break

        return nodes_to_trigger

    def get_l2(
        self,
        market_index: int,
        market_type: MarketType,
        slot: int,
        oracle_price_data: OraclePriceData,
        depth: int,
        fallback_l2_generators: List[L2OrderBookGenerator] = [],
    ) -> L2OrderBook:
        """
        get an l2 view of the orderbook for a given market
        """

        maker_ask_l2_level_generator = get_l2_generator_from_dlob_nodes(
            self.get_resting_limit_asks(
                market_index, slot, market_type, oracle_price_data
            ),
            oracle_price_data,
            slot,
        )

        fallback_ask_generators = [
            fallback_l2_generator.get_l2_asks()
            for fallback_l2_generator in fallback_l2_generators
        ]

        ask_l2_level_generator = merge_l2_level_generators(
            [maker_ask_l2_level_generator] + fallback_ask_generators,
            lambda a, b: a.price < b.price,
        )

        asks = create_l2_levels(ask_l2_level_generator, depth)

        maker_bid_l2_level_generator = get_l2_generator_from_dlob_nodes(
            self.get_resting_limit_bids(
                market_index, slot, market_type, oracle_price_data
            ),
            oracle_price_data,
            slot,
        )

        fallback_bid_generators = [
            fallback_l2_generator.get_l2_bids()
            for fallback_l2_generator in fallback_l2_generators
        ]

        bid_l2_level_generator = merge_l2_level_generators(
            [maker_bid_l2_level_generator] + fallback_bid_generators,
            lambda a, b: a.price > b.price,
        )

        bids = create_l2_levels(bid_l2_level_generator, depth)

        return L2OrderBook(asks, bids, slot)

    def get_l3(
        self,
        market_index: int,
        market_type: MarketType,
        slot: int,
        oracle_price_data: OraclePriceData,
    ) -> L3OrderBook:
        """
        get an l3 view of the orderbook for a given market
        """

        bids: List[L3Level] = []
        asks: List[L3Level] = []

        resting_asks = self.get_resting_limit_asks(
            market_index, slot, market_type, oracle_price_data
        )

        for ask in resting_asks:
            asks.append(
                L3Level(
                    price=ask.get_price(oracle_price_data, slot),
                    size=ask.order.base_asset_amount
                    - ask.order.base_asset_amount_filled,
                    maker=ask.user_account,
                    order_id=ask.order.order_id,
                )
            )

        resting_bids = self.get_resting_limit_bids(
            market_index, slot, market_type, oracle_price_data
        )

        for bid in resting_bids:
            bids.append(
                L3Level(
                    price=bid.get_price(oracle_price_data, slot),
                    size=bid.order.base_asset_amount
                    - bid.order.base_asset_amount_filled,
                    maker=bid.user_account,
                    order_id=bid.order.order_id,
                )
            )

        return L3OrderBook(asks, bids, slot)
