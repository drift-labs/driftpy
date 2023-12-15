from typing import Callable, List
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