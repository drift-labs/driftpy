from abc import ABC, abstractmethod
from typing import Literal
from solders.pubkey import Pubkey
from driftpy.constants.numeric_constants import AMM_RESERVE_PRECISION, PRICE_PRECISION
from driftpy.math.conversion import convert_to_number
from driftpy.math.orders import get_limit_price
from driftpy.types import OraclePriceData, Order, is_variant


class DLOBNode(ABC):
    @abstractmethod
    def get_price(self, oracle_price_data: OraclePriceData, slot: int) -> int:
        pass

    @abstractmethod
    def is_vamm_node(self) -> bool:
        pass

    @abstractmethod
    def is_base_filled(self) -> bool:
        pass


class VAMMNode(DLOBNode):
    def __init__(self, price: int):
        self.price = price
        self.order = None

    def get_price(self, oracle_price_data: OraclePriceData, slot: int) -> int:
        return self.price

    def is_vamm_node(self) -> bool:
        return True

    def is_base_filled(self) -> bool:
        return False


class OrderNode(DLOBNode):
    def __init__(self, order: Order, user_account: Pubkey):
        self.order = order
        self.user_account = user_account
        self.sort_value = self.get_sort_value(order)
        self.have_filled = False
        self.have_trigger = False

    @abstractmethod
    def get_sort_value(self, order: Order):
        pass

    def get_label(self):
        from driftpy.dlob.node_list import get_order_signature

        msg = f"Order {get_order_signature(self.order.order_id, self.user_account)}"
        direction = "Long" if is_variant(self.order.direction, "Long") else "Short"
        msg += f" {direction} {convert_to_number(self.order.base_asset_amount, AMM_RESERVE_PRECISION):.3f}"
        if self.order.price > 0:
            msg += f" @ {convert_to_number(self.order.price, PRICE_PRECISION):.3f}"
        if self.order.trigger_price > 0:
            condition = (
                "Below"
                if is_variant(self.order.trigger_condition, "Below")
                else "Above"
            )
            msg += f" {condition} {convert_to_number(self.order.trigger_price, PRICE_PRECISION):.3f}"
        return msg

    def get_price(self, oracle_price_data: OraclePriceData, slot: int):
        return get_limit_price(self.order, oracle_price_data, slot)

    def is_base_filled(self) -> bool:
        return self.order.base_asset_amount_filled == self.order.base_asset_amount

    def is_vamm_node(self):
        return False


class TakingLimitOrderNode(OrderNode):
    def __init__(self, order: Order, user_account: Pubkey):
        super().__init__(order, user_account)
        self.next = None
        self.previous = None

    def get_sort_value(self, order: Order) -> int:
        return order.slot


class RestingLimitOrderNode(OrderNode):
    def __init__(self, order: Order, user_account: Pubkey):
        super().__init__(order, user_account)
        self.next = None
        self.previous = None

    def get_sort_value(self, order: Order) -> int:
        return order.price


class FloatingLimitOrderNode(OrderNode):
    def __init__(self, order: Order, user_account: Pubkey):
        super().__init__(order, user_account)
        self.next = None
        self.previous = None

    def get_sort_value(self, order: Order) -> int:
        return order.oracle_price_offset


class MarketOrderNode(OrderNode):
    def __init__(self, order: Order, user_account: Pubkey):
        super().__init__(order, user_account)
        self.next = None
        self.previous = None

    def get_sort_value(self, order: Order) -> int:
        return order.slot


class TriggerOrderNode(OrderNode):
    def __init__(self, order: Order, user_account: Pubkey):
        super().__init__(order, user_account)
        self.next = None
        self.previous = None

    def get_sort_value(self, order: Order) -> int:
        return order.trigger_price


NodeType = Literal["restingLimit", "takingLimit", "floatingLimit", "market", "trigger"]

SortDirection = Literal["asc", "desc"]

node_type_map: dict[NodeType, type] = {
    "restingLimit": RestingLimitOrderNode,
    "takingLimit": TakingLimitOrderNode,
    "floatingLimit": FloatingLimitOrderNode,
    "market": MarketOrderNode,
    "trigger": TriggerOrderNode,
}


def create_node(node_type: NodeType, order: Order, user_account: Pubkey):
    node_class = node_type_map.get(node_type)
    if node_class is not None:
        return node_class(order, user_account)
    else:
        raise ValueError(f"Unknown DLOBNode type {node_type}")
