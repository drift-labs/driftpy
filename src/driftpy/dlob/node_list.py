from typing import Generator, Generic, TypeVar

from solders.pubkey import Pubkey

from driftpy.dlob.dlob_node import (
    DLOBNode,
    NodeType,
    SortDirection,
    VAMMNode,
    create_node,
)
from driftpy.types import Order, is_variant

T = TypeVar("T", bound=DLOBNode)


def get_order_signature(order_id: int, user_account: Pubkey) -> str:
    return f"{str(user_account)}-{str(order_id)}"


class NodeList(Generic[T]):
    def __init__(self, node_type: NodeType, sort_direction: SortDirection):
        self.head = None
        self.length = 0
        self.node_map = {}
        self.node_type: NodeType = node_type
        self.sort_direction = sort_direction

    def clear(self):
        self.head = None
        self.length = 0
        self.node_map.clear()

    def insert(self, order: Order, market_type, user_account: Pubkey):
        if not is_variant(order.status, "Open"):
            return

        new_node = create_node(self.node_type, order, user_account)

        order_signature = get_order_signature(order.order_id, user_account)
        if order_signature in self.node_map:
            return

        self.node_map[order_signature] = new_node
        self.length += 1

        if self.head is None:
            self.head = new_node
            return

        if self.prepend_node(self.head, new_node):
            self.head.previous = new_node
            new_node.next = self.head
            self.head = new_node
            return

        current_node = self.head
        while current_node.next is not None and not self.prepend_node(
            current_node.next, new_node
        ):
            current_node = current_node.next

        new_node.next = current_node.next
        if current_node.next is not None:
            new_node.next.previous = new_node
        current_node.next = new_node
        new_node.previous = current_node

    def prepend_node(self, current_node: T, new_node: T) -> bool:
        current_order = current_node.order
        new_order = new_node.order

        current_order_sort_price = current_node.sort_value
        new_order_sort_price = new_node.sort_value

        if new_order_sort_price == current_order_sort_price:
            return new_order.slot < current_order.slot

        if self.sort_direction == "asc":
            return new_order_sort_price < current_order_sort_price
        else:
            return new_order_sort_price > current_order_sort_price

    def update(self, order: Order, user_account: Pubkey):
        order_id = get_order_signature(order.order_id, user_account)
        if order_id in self.node_map:
            node = self.node_map[order_id]
            node.order = order
            node.have_filled = False

    def remove(self, order: Order, user_account: Pubkey):
        order_id = get_order_signature(order.order_id, user_account)
        if order_id in self.node_map:
            node = self.node_map.pop(order_id)

            if node.next:
                node.next.previous = node.previous
            if node.previous:
                node.previous.next = node.next

            if self.head and self.head.order.order_id == order.order_id:
                self.head = node.next

            self.length -= 1

    def get_generator(self) -> Generator[DLOBNode, None, None]:
        node = self.head
        while node:
            yield node
            node = node.next

    def has(self, order: Order, user_account: Pubkey):
        return get_order_signature(order.order_id, user_account) in self.node_map

    def get(self, order_signature):
        return self.node_map.get(order_signature)

    def print_list(self):
        current_node = self.head
        while current_node:
            print(current_node.get_label())
            current_node = current_node.next

    def print_top(self):
        if self.head:
            print(self.sort_direction.upper(), self.head.get_label())
        else:
            print("---")


def get_vamm_node_generator(price) -> Generator[DLOBNode, None, None]:
    if price is not None:
        yield VAMMNode(price)
