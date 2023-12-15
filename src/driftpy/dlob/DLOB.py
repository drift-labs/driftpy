import copy
from typing import Callable, Dict, List, Optional
from solders.pubkey import Pubkey
from driftpy.dlob.DLOB_generators import get_node_lists
from driftpy.dlob.DLOB_helpers import add_order_list, get_list_identifiers
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
from driftpy.math.orders import is_resting_limit_order
from driftpy.types import Order, is_variant, is_one_of_variant, market_type_to_string

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

        type, subtype = get_list_identifiers(order, slot)

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
        on_update: Optional[OrderBookCallback]
    ):
        self.update_resting_limit_orders(slot)

        if order.base_asset_amount == cumulative_base_asset_amount_filled:
            self.delete(order, user_account, slot)
            return
        
        if order.base_asset_amount_filled == cumulative_base_asset_amount_filled:
            return
        
        new_order = copy.deepcopy(order)

        new_order.base_asset_amount_filled = cumulative_base_asset_amount_filled

        type, subtype = get_list_identifiers(order, slot)

        market_type = market_type_to_string(order.market_type)

        node_list = self.order_lists.get(market_type, {}).get(order.market_index, None)

        target_list = getattr(node_list, type, {}).get(subtype, None)

        if target_list is not None:
            target_list: NodeList
            target_list.update(order, user_account)

        if on_update is not None and callable(on_update):
            on_update()
    






