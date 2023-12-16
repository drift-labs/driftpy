import copy
from typing import Callable, Dict, Generator, List, Optional, Union
from solders.pubkey import Pubkey
from driftpy.dlob.DLOB_generators import get_node_lists
from driftpy.dlob.DLOB_helpers import add_order_list, get_list_identifiers, get_maker_rebate
from driftpy.dlob.node_list import get_order_signature, get_vamm_node_generator, NodeList
from driftpy.dlob.orderbook_levels import (
    create_l2_levels,
    merge_l2_level_generators,
    get_l2_generator_from_dlob_nodes, 
    L2Level, 
    L2OrderBook, 
    L2OrderBookGenerator,
    L3Level,
    L3OrderBook
)
from driftpy.dlob.DLOB_orders import DLOBOrders
from driftpy.dlob.DLOB_node import (
    NodeType,
    DLOBNode, 
    RestingLimitOrderNode,
    FloatingLimitOrderNode,
    TakingLimitOrderNode,
    MarketOrderNode,
    TriggerOrderNode
)
from driftpy.math.auction import is_fallback_available_liquidity_source
from driftpy.math.exchange_status import fill_paused, amm_paused
from driftpy.math.orders import get_limit_price, is_order_expired, is_resting_limit_order, is_triggered
from driftpy.types import MarketType, OraclePriceData, Order, OrderActionRecord, OrderRecord, PerpMarketAccount, SpotMarketAccount, StateAccount, is_variant, is_one_of_variant, market_type_to_string

class MarketNodeLists:
    def __init__(self):
        self.resting_limit = {
            "ask": NodeList[RestingLimitOrderNode](),
            "bid": NodeList[RestingLimitOrderNode](),
        }
        self.floating_limit = {
            "ask": NodeList[FloatingLimitOrderNode](),
            "bid": NodeList[FloatingLimitOrderNode](),
        }
        self.taking_limit = {
            "ask": NodeList[TakingLimitOrderNode](),
            "bid": NodeList[TakingLimitOrderNode](),
        }
        self.market = {
            "ask": NodeList[MarketOrderNode](),
            "bid": NodeList[MarketOrderNode](),
        }
        self.trigger = {
            "above": NodeList[TriggerOrderNode](),
            "below": NodeList[TriggerOrderNode](),
        }

OrderBookCallback = Callable([], None)
'''
    Receives a DLOBNode and is expected to return True if the node should
    be taken into account when generating, or False otherwise

    Currentl used in get_resting_limit_bids and get_resting_limit_asks
'''
DLOBFilterFcn = Callable[[DLOBNode], bool]

class NodeToFill:
    def __init__(self, node: DLOBNode, maker_nodes: List[DLOBNode]):
        self.node = node
        self.maker = maker_nodes

class NodeToTrigger:
    def __init__(self, node: TriggerOrderNode):
        self.node = node

SUPPORTED_ORDER_TYPES = [
    'market',
    'limit',
    'triggerMarket',
    'triggerLimit',
    'oracle',
]

class DLOB:

    def __init__(self):
        self.open_orders: Dict[str, set] = {}
        self.order_lists: Dict[str, Dict[int, MarketNodeLists]] = {}
        self.max_slot_for_resting_limit_orders = 0
        self.initialized = False
        self.init()

    def init(self):
        self.open_orders['perp'] = set()
        self.open_orders['spot'] = set()
        self.order_lists['perp'] = {}
        self.order_lists['spot'] = {}

    def insert_order(
        self,
        order: Order, 
        user_account: Pubkey, 
        slot: int, 
        on_insert: Optional[OrderBookCallback] = None
    ):
        if is_variant(order.status, "Init"):
            return
        
        if not is_one_of_variant(order.order_type, SUPPORTED_ORDER_TYPES):
            return
        
        market_type = market_type_to_string(order.market_type)

        if not order.market_index in self.order_lists.get(market_type):
            self.order_lists = add_order_list(market_type, order.market_index, self.order_lists)

        if is_variant(order.status, "Open"):
            self.open_orders.get(market_type).add(get_order_signature(order.order_id, user_account))

        type, subtype = get_list_identifiers(order, slot, self.order_lists)

        node_list = self.order_lists.get(market_type, {}).get(order.market_index, None)

        target_list = getattr(node_list, type, {}).get(subtype, None)

        if target_list is not None:
            target_list: NodeList
            target_list.insert(order, market_type, user_account)

        if on_insert is not None and callable(on_insert):
            on_insert()

    def get_order(self, order_id: int, user_account: Pubkey) -> Optional[Order]:
        order_signature = get_order_signature(order_id, user_account)
        for node_list in get_node_lists(self.order_lists):
            node = node_list.get(order_signature)
            if node:
                return node.order
            
        return None
    
    def _update_resting_limit_orders_for_market_type(self, slot: int, market_type_str: str):

        if market_type_str not in self.order_lists:
            return
        
        for _, node_lists in self.order_lists[market_type_str].items():
            nodes_to_update = []

            for node in node_lists.taking_limit['ask'].get_generator():
                if not is_resting_limit_order(node.order, slot):
                    continue
                nodes_to_update.append({
                    'side': 'ask',
                    'node': node
                })

            for node in node_lists.taking_limit['bid'].get_generator():
                if not is_resting_limit_order(node.order, slot):
                    continue
                nodes_to_update.append({
                    'side': 'bid',
                    'node': node
                })

            for node_to_update in nodes_to_update:
                side = node_to_update['side']
                node = node_to_update['node']
                node_lists.taking_limit[side].remove(node.order, node.user_account)
                node_lists.resting_limit[side].insert(node.order, market_type_str, node.user_account)

    def update_resting_limit_orders(self, slot: int):
        if slot < self.max_slot_for_resting_limit_orders:
            return
        
        self.max_slot_for_resting_limit_orders = slot

        self.update_resting_limit_orders_for_market_type(slot, 'perp')
        self.update_resting_limit_orders_for_market_type(slot, 'spot')
    
    def update_order(
        self,
        order: Order,
        user_account: Pubkey,
        slot: int,
        cumulative_base_asset_amount_filled: int,
        on_update: Optional[OrderBookCallback] = None
    ):
        self.update_resting_limit_orders(slot)

        if order.base_asset_amount == cumulative_base_asset_amount_filled:
            self.delete(order, user_account, slot)
            return
        
        if order.base_asset_amount_filled == cumulative_base_asset_amount_filled:
            return
        
        new_order = copy.deepcopy(order)

        new_order.base_asset_amount_filled = cumulative_base_asset_amount_filled

        type, subtype = get_list_identifiers(order, slot, self.order_lists)

        market_type = market_type_to_string(order.market_type)

        node_list = self.order_lists.get(market_type, {}).get(order.market_index, None)

        target_list = getattr(node_list, type, {}).get(subtype, None)

        if target_list is not None:
            target_list: NodeList
            target_list.update(order, user_account)

        if on_update is not None and callable(on_update):
            on_update()
    
    def delete(
        self,
        order: Order,
        user_account: Pubkey,
        slot: int,
        on_delete: Optional[OrderBookCallback] = None
    ):
        if is_variant(order.status, 'Init'):
            return
        
        self.update_resting_limit_orders(slot)

        type, subtype = get_list_identifiers(order, slot, self.order_lists)

        market_type = market_type_to_string(order.market_type)

        node_list = self.order_lists.get(market_type, {}).get(order.market_index, None)

        target_list = getattr(node_list, type, {}).get(subtype, None)

        if target_list is not None:
            target_list: NodeList
            target_list.remove(order, user_account)

        if on_delete is not None and callable(on_delete):
            on_delete()

    def clear(self):
        for market_type in self.open_orders.keys():
            self.open_orders.get(market_type).clear()

        self.open_orders.clear()

        for market_type in self.order_lists.keys():
            for market_index in self.order_lists.get(market_type).keys():
                node_lists: MarketNodeLists = self.order_lists.get(market_type).get(market_index)

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
        on_trigger: Optional[OrderBookCallback] = None
    ):
        if is_variant(order, 'Init'):
            return
        
        self.update_resting_limit_orders(slot)

        if is_triggered(order):
            return
        
        market_type = market_type_to_string(order.market_type)

        trigger_list = self.order_lists.get(market_type).get(order.market_index) \
            .trigger['above' if is_variant(order.trigger_condition, 'above') else 'below']
        trigger_list.remove(order, user_account)

        type, subtype = get_list_identifiers(order, slot, self.order_lists)

        node_list = self.order_lists.get(market_type, {}).get(order.market_index, None)

        target_list = getattr(node_list, type, {}).get(subtype, None)

        if target_list is not None:
            target_list: NodeList
            target_list.insert(order, market_type, user_account)

        if on_trigger is not None and callable(on_trigger):
            on_trigger()

    def handle_order_record(self, record: OrderRecord, slot: int):
        self.insert_order(record.order, record.user, slot)

    def handle_order_action_record(self, record: OrderActionRecord, slot: int):
        if is_one_of_variant(record.action, ['PLACE', 'EXPIRE']):
            return
        
        if is_variant(record.action, 'TRIGGER'):
            if record.taker is not None:
                taker_order = self.get_order(record.taker_order_id, record.taker)
                if taker_order is not None:
                    self.trigger(taker_order, record.taker, slot)

            if record.maker is not None:
                maker_order = self.get_order(record.maker_order_id, record.maker)
                if maker_order is not None:
                    self.trigger(maker_order, record.maker, slot)
        elif is_variant(record.action, 'FILL'):
            if record.taker is not None:
                taker_order = self.get_order(record.taker_order_id, record.taker)
                if taker_order is not None:
                    self.update_order(taker_order, record.taker, slot, record.taker_order_cumulative_base_asset_amount_filled)

            if record.maker is not None:
                maker_order = self.get_order(record.maker_order_id, record.maker)
                if maker_order is not None:
                    self.update_order(maker_order, record.maker, slot, record.maker_order_cumulative_base_asset_amount_filled)
        elif is_variant(record.action, 'CANCEL'):
            if record.taker is not None:
                taker_order = self.get_order(record.taker_order_id, record.taker)
                if taker_order is not None:
                    self.delete(taker_order, record.taker, slot)

            if record.maker is not None:
                maker_order = self.get_order(record.maker_order_id, record.maker)
                if maker_order is not None:
                    self.delete(maker_order, record.maker, slot)
    
    def _get_best_node(
        self,
        generator_list: List[Generator[DLOBNode, None, None]],
        oracle_price_data: OraclePriceData,
        slot: int,
        compare_fcn: Callable[[DLOBNode, DLOBNode, int, OraclePriceData], bool],
        filter_fcn: Optional[DLOBFilterFcn] = None
    ) -> Generator[DLOBNode, None, None]:
        
        generators = [{'next': next(generator, None), 'generator': generator} for generator in generator_list]

        side_exhausted = False
        while not side_exhausted:
            best_generator = None
            for current_generator in generators:
                if current_generator['next'] is None:
                    continue

                if best_generator is None or compare_fcn(best_generator['next'], current_generator['next'], slot, oracle_price_data):
                    best_generator = current_generator

            if best_generator and best_generator['next']:
                # Skip this node is it's already completely filled or fails filter function
                if best_generator['next'].is_base_filled() or (filter_fcn and not filter_fcn(best_generator['next'])):
                    best_generator['next'] = next(best_generator['generator'], None)
                    continue

                yield best_generator['next']
                best_generator['next'] = next(best_generator['generator'])
            else:
                side_exhausted = True

    def get_resting_limit_asks(
        self,
        market_index: int,
        slot: int,
        market_type: MarketType,
        oracle_price_data: OraclePriceData,
        filter_fcn: Optional[DLOBFilterFcn] = None
    ) -> Generator[DLOBNode, None, None]:
        if is_variant(market_type, 'Spot') and not oracle_price_data:
            raise ValueError("Must provide oracle price data to get spot asks")
        
        self.update_resting_limit_orders(slot)

        market_type_str = market_type_to_string(market_type)
        node_lists = self.order_lists.get(market_type_str, {}).get(market_index)

        if node_lists is None:
            return
        
        generator_list = [
            node_lists.resting_limit['ask'].get_generator(),
            node_lists.floating_limit['ask'].get_generator()
        ]

        yield from self._get_best_node(
            generator_list,
            oracle_price_data,
            slot,
            lambda best_node, current_node, slot, oracle_price_data: best_node.get_price(oracle_price_data, slot) < current_node.get_price(oracle_price_data, slot),
            filter_fcn
        )

    def get_resting_limit_bids(
        self,
        market_index: int,
        slot: int,
        market_type: MarketType,
        oracle_price_data: OraclePriceData,
        filter_fcn: Optional[DLOBFilterFcn] = None
    ) -> Generator[DLOBNode, None, None]:
        if is_variant(market_type, 'Spot') and not oracle_price_data:
            raise ValueError("Must provide oracle price data to get spot bids")
        
        self.update_resting_limit_orders(slot)

        market_type_str = market_type_to_string(market_type)
        node_lists = self.order_lists.get(market_type_str, {}).get(market_index)

        if node_lists is None:
            return
        
        generator_list = [
            node_lists.resting_limit['bid'].get_generator(),
            node_lists.floating_limit['bid'].get_generator()
        ]

        yield from self._get_best_node(
            generator_list,
            oracle_price_data,
            slot,
            lambda best_node, current_node, slot, oracle_price_data: best_node.get_price(oracle_price_data, slot) < current_node.get_price(oracle_price_data, slot),
            filter_fcn
        )

    def get_taking_bids(
        self,
        market_index: int,
        market_type: MarketType,
        slot: int,
        oracle_price_data: OraclePriceData
    ) -> Generator[DLOBNode, None, None]:
        market_type_str = market_type_to_string(market_type)
        order_lists = self.order_lists.get(market_type_str, {}).get(market_index)

        if order_lists is None:
            return
        
        self.update_resting_limit_orders(slot)

        generator_list = List[
            order_lists.market['bid'].get_generator(),
            order_lists.taking_limit['bid'].get_generator()
        ]

        yield from self._get_best_node(
            generator_list,
            oracle_price_data,
            slot,
            lambda best_node, current_node: best_node.order.slot < current_node.order.slot
        )

    def get_taking_asks(
        self,
        market_index: int,
        market_type: MarketType,
        slot: int,
        oracle_price_data: OraclePriceData
    ) -> Generator[DLOBNode, None, None]:
        market_type_str = market_type_to_string(market_type)
        order_lists = self.order_lists.get(market_type_str, {}).get(market_index)

        if order_lists is None:
            return
        
        self.update_resting_limit_orders(slot)

        generator_list = List[
            order_lists.market['ask'].get_generator(),
            order_lists.market['ask'].get_generator()
        ]

        yield from self._get_best_node(
            generator_list,
            oracle_price_data,
            slot,
            lambda best_node, current_node: best_node.order.slot < current_node.order.slot
        )

    def find_nodes_crossing_fallback_liquidity(
        self,
        market_type: MarketType,
        slot: int,
        oracle_price_data: OraclePriceData,
        node_generator: Generator[DLOBNode, None, None],
        does_cross: Callable[[Optional[int]], bool],
        min_auction_duration: int
    ) -> List[NodeToFill]:
        nodes_to_fill = []

        for node in node_generator:
            if is_variant(market_type, 'Spot') and node.order.post_only:
                continue

            node_price = get_limit_price(node.order, oracle_price_data, slot)

            crosses = does_cross(node_price)

            fallback_available = (
                is_variant(market_type, 'Spot') or
                is_fallback_available_liquidity_source(node.order, min_auction_duration, slot)
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
        maker_node_generator_fn: Callable[[int, int, MarketType, OraclePriceData], Generator[DLOBNode, None, None]],
        does_cross: Callable[[int, int], bool]
    ) -> List[NodeToFill]:
        nodes_to_fill: List[NodeToFill] = []

        for taker_node in taker_node_generator:
            maker_node_generator = maker_node_generator_fn(market_index, slot, market_type, oracle_price_data)

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
                maker_base_remaining = maker_node.order.base_asset_amount - maker_node.order.base_asset_amount_filled
                taker_base_remaining = taker_node.order.base_asset_amount - taker_node.order.base_asset_amount_filled

                base_filled = min(maker_base_remaining, taker_base_remaining)

                new_maker_order = copy.deepcopy(maker_node.order)
                new_maker_order.base_asset_amount_filled += base_filled

                type, subtype = get_list_identifiers(new_maker_order, slot, self.order_lists)

                market_type = market_type_to_string(new_maker_order.market_type)

                node_list = self.order_lists.get(market_type, {}).get(new_maker_order.market_index, None)

                target_list = getattr(node_list, type, {}).get(subtype, None)

                if target_list is not None:
                    target_list: NodeList
                    target_list.update(new_maker_order, maker_node.user_account)

                new_taker_order = copy.deepcopy(taker_node.order)
                new_taker_order.base_asset_amount_filled += base_filled

                type, subtype = get_list_identifiers(new_taker_order, slot, self.order_lists)

                market_type = market_type_to_string(new_maker_order.market_type)

                node_list = self.order_lists.get(market_type, {}).get(new_maker_order.market_index, None)

                target_list = getattr(node_list, type, {}).get(subtype, None)

                if target_list is not None:
                    target_list: NodeList
                    target_list.update(new_taker_order, taker_node.user_account)

                if new_taker_order.base_asset_amount_filled == taker_node.order.base_asset_amount:
                    break
        
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
        nodes_to_fill: List[NodeToFill] = []

        # Process taking asks
        taking_order_generator = self.get_taking_asks(market_index, market_type, slot, oracle_price_data)
        maker_node_generator_fn = lambda: self.get_resting_limit_bids(market_index, market_type, slot, oracle_price_data)
        does_cross = lambda taker_price, maker_price: (taker_price is None or taker_price <= maker_price) if (not is_variant(market_type, 'Spot') or (fallback_bid and maker_price < fallback_bid)) else False
        taking_asks_crossing_bids = self.find_taking_nodes_crossing_maker_nodes(
            market_index,
            slot,
            market_type,
            oracle_price_data,
            taking_order_generator,
            maker_node_generator_fn,
            does_cross
        )
        nodes_to_fill.extend(taking_asks_crossing_bids)

        # Process fallback asks
        if fallback_bid is not None and not is_amm_paused:
            taking_order_generator = self.get_taking_asks(market_index, market_type, slot, oracle_price_data)
            does_cross = lambda taker_price: taker_price is None or taker_price <= fallback_bid,
            taking_asks_crossing_fallback = self.find_nodes_crossing_fallback_liquidity(
                market_type,
                slot,
                oracle_price_data,
                taking_order_generator,
                does_cross,
                min_auction_duration
            )
            nodes_to_fill.extend(taking_asks_crossing_fallback)

        # Process taking bids
        taking_order_generator = self.get_taking_bids(market_index, market_type, slot, oracle_price_data)
        maker_node_generator_fn = lambda: self.get_resting_limit_asks(market_index, market_type, slot, oracle_price_data)
        does_cross = lambda taker_price, maker_price: (taker_price is None or taker_price >= maker_price) if (not is_variant(market_type, 'Spot') or (fallback_bid and maker_price > fallback_bid)) else False
        taking_bids_to_fill = self.find_taking_nodes_crossing_maker_nodes(
            market_index,
            slot,
            market_type,
            oracle_price_data,
            taking_order_generator,
            maker_node_generator_fn,
            does_cross
        )
        nodes_to_fill.extend(taking_bids_to_fill)

        # Process fallback bids
        if fallback_ask is not None and not is_amm_paused:
            taking_order_generator = self.get_taking_bids(market_index, market_type, slot, oracle_price_data)
            does_cross = lambda taker_price: taker_price is None or taker_price >= fallback_ask,
            taking_bids_crossing_fallback = self.find_nodes_crossing_fallback_liquidity(
                market_type,
                slot,
                oracle_price_data,
                taking_order_generator,
                does_cross,
                min_auction_duration
            )
            nodes_to_fill.extend(taking_bids_crossing_fallback)
        
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

        crossing_nodes = self.find_crossing_resting_limit_orders(market_index, slot, market_type, oracle_price_data)

        for crossing_node in crossing_nodes:
            nodes_to_fill.append(crossing_node)

        if fallback_bid is not None and not is_amm_paused:
            ask_generator = self.get_resting_limit_asks(market_index, slot, market_type, oracle_price_data)

            fallback_bid_with_buffer = fallback_bid - (fallback_bid * maker_rebate_numerator // maker_rebate_denominator)

            asks_crossing_fallback = self.find_nodes_crossing_fallback_liquidity(
                market_type, 
                slot, 
                oracle_price_data, 
                ask_generator,
                lambda ask_price: ask_price <= fallback_bid_with_buffer,
                min_auction_duration
            )

            for ask_crossing_fallback in asks_crossing_fallback:
                nodes_to_fill.append(ask_crossing_fallback)


        if fallback_ask is not None and not is_amm_paused:
            bid_generator = self.get_resting_limit_bids(market_index, slot, market_type, oracle_price_data)

            fallback_ask_with_buffer = fallback_ask + (fallback_ask * maker_rebate_numerator // maker_rebate_denominator)

            bids_crossing_fallback = self.find_nodes_crossing_fallback_liquidity(
                market_type,
                slot,
                oracle_price_data,
                bid_generator,
                lambda bid_price: bid_price >= fallback_ask_with_buffer,
                min_auction_duration
            )

            for bid_crossing_fallback in bids_crossing_fallback:
                nodes_to_fill.append(bid_crossing_fallback)

        return nodes_to_fill
    
    def find_expired_nodes_to_fill(
        self,
        market_index: int,
        ts: int,
        market_type: MarketType
    ) -> List[NodeToFill]:
        nodes_to_fill: List[NodeToFill] = []

        market_type_str = market_type_to_string(market_type)
        node_lists = self.order_lists.get(market_type_str, {}).get(market_index)

        if node_lists is None:
            return nodes_to_fill
        
        bid_generators = [
            node_lists.taking_limit['bid'].get_generator(),
            node_lists.resting_limit['bid'].get_generator(),
            node_lists.floating_limit['bid'].get_generator(),
            node_lists.market['bid'].get_generator(),
        ]
        ask_generators = [
            node_lists.taking_limit['ask'].get_generator(),
            node_lists.resting_limit['ask'].get_generator(),
            node_lists.floating_limit['ask'].get_generator(),
            node_lists.market['ask'].get_generator(),
        ]

        for bid_generator in bid_generators:
            for bid in bid_generator:
                if is_order_expired(bid.order, ts, True):
                    nodes_to_fill.append(NodeToFill(bid, []))
                    
        for ask_generator in ask_generators:
            for ask in ask_generator:
                if is_order_expired(bid.order, ts, True):
                    nodes_to_fill.append(NodeToFill(ask, []))
    
    def merge_nodes_to_fill(
        resting_limit_order_nodes_to_fill: List[NodeToFill],
        taking_order_nodes_to_fill: List[NodeToFill],
    ) -> List[NodeToFill]:
        merged_nodes_to_fill: Dict[str, NodeToFill] = {}

        def merge_nodes_to_fill_helper(nodes_to_fill_list):
            for node_to_fill in nodes_to_fill_list:
                node_signature = get_order_signature(node_to_fill.node.order.order_id, node_to_fill.node.user_account)

                if node_signature not in merged_nodes_to_fill:
                    merged_nodes_to_fill[node_signature] = NodeToFill(node_to_fill.node, [])
                
                if node_to_fill.maker_nodes is not None:
                    merged_nodes_to_fill[node_signature].maker_nodes.extend(node_to_fill.maker_nodes)
        
        merge_nodes_to_fill_helper(resting_limit_order_nodes_to_fill)
        merge_nodes_to_fill_helper(taking_order_nodes_to_fill)

        return list[merged_nodes_to_fill.values()]

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

        min_auction_duration = state_account.min_perp_auction_duration if is_variant(market_type, 'Perp') else 0

        maker_rebate_numerator, maker_rebate_denominator = get_maker_rebate(market_type, state_account, market_account)

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
            fallback_bid
        )

        taking_order_nodes_to_fill = self.find_taking_nodes_to_fill(
            market_index,
            slot,
            market_type,
            oracle_price_data,
            is_amm_paused,
            min_auction_duration,
            fallback_ask,
            fallback_bid
        )

        expired_nodes_to_fill = self.find_expired_nodes_to_fill(
            market_index,
            ts,
            market_type
        )
        
        # for spot, multiple makers isn't supported, so don't fill
        if is_variant(market_type, 'Spot'):
            return resting_limit_order_nodes_to_fill + taking_order_nodes_to_fill + expired_nodes_to_fill
        
        return self.merge_nodes_to_fill(
            resting_limit_order_nodes_to_fill,
            taking_order_nodes_to_fill
        ) + expired_nodes_to_fill
    




