from typing import Optional, Dict, List
from dataclasses import dataclass

from driftpy.events.types import WrappedEvent


@dataclass
class Node:
    key: str
    value: List[WrappedEvent]
    next: Optional[any] = None
    prev: Optional[any] = None


class TxEventCache:
    def __init__(self, max_tx: int = 1024):
        self.size = 0
        self.max_tx = max_tx
        self.head = None
        self.tail = None
        self.cache_map: Dict[str, Node] = {}

    def add(self, key: str, events: List[WrappedEvent]) -> None:
        existing_node = self.cache_map.get(key)
        if existing_node:
            self.detach(existing_node)
            self.size -= 1
        elif self.size == self.max_tx:
            del self.cache_map[self.tail.key]
            self.detach(self.tail)
            self.size -= 1

        if not self.head:
            self.head = self.tail = Node(key, events)
        else:
            node = Node(key, events, next=self.head)
            self.head.prev = node
            self.head = node

        self.cache_map[key] = self.head
        self.size += 1

    def has(self, key: str) -> bool:
        return key in self.cache_map

    def get(self, key: str) -> Optional[List[WrappedEvent]]:
        return self.cache_map.get(key).value if key in self.cache_map else None

    def detach(self, node: Node) -> None:
        if node.prev is not None:
            node.prev.next = node.next
        else:
            self.head = node.next

        if node.next is not None:
            node.next.prev = node.prev
        else:
            self.tail = node.prev

    def clear(self) -> None:
        self.head = None
        self.tail = None
        self.size = 0
        self.cache_map = {}
