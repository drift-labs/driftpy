from typing import Optional
from dataclasses import dataclass

from driftpy.events.types import WrappedEvent, EventSubscriptionOrderDirection, SortFn


@dataclass
class Node:
    event: WrappedEvent
    next: Optional[any] = None
    prev: Optional[any] = None


class EventList:
    def __init__(
        self,
        max_size: int,
        sort_fn: SortFn,
        order_direction: EventSubscriptionOrderDirection,
    ):
        self.size = 0
        self.max_size = max_size
        self.sort_fn = sort_fn
        self.order_direction = order_direction
        self.head = None
        self.tail = None

    def insert(self, event: WrappedEvent) -> None:
        self.size += 1
        new_node = Node(event)
        if self.head is None:
            self.head = self.tail = new_node
            return

        halt_condition = -1 if self.order_direction == "asc" else 1

        if self.sort_fn(self.head.event, new_node.event) == halt_condition:
            self.head.prev = new_node
            new_node.next = self.head
            self.head = new_node
        else:
            current_node = self.head
            while (
                current_node.next is not None
                and self.sort_fn(current_node.next.event, new_node.event)
                != halt_condition
            ):
                current_node = current_node.next

            new_node.next = current_node.next
            if current_node.next is not None:
                new_node.next.prev = new_node
            else:
                self.tail = new_node

            current_node.next = new_node
            new_node.prev = current_node

        if self.size > self.max_size:
            self.detach()

    def detach(self) -> None:
        node = self.tail
        if node.prev is not None:
            node.prev.next = node.next
        else:
            self.head = node.next

        if node.next is not None:
            node.next.prev = node.prev
        else:
            self.tail = node.prev

        self.size -= 1

    def to_array(self) -> list[WrappedEvent]:
        return list(self)

    def __iter__(self):
        node = self.head
        while node:
            yield node.event
            node = node.next
