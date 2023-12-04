from driftpy.events.types import (
    WrappedEvent,
    EventSubscriptionOrderBy,
    EventSubscriptionOrderDirection,
    SortFn,
)


def client_sort_asc_fn() -> int:
    return -1


def client_sort_desc_fn() -> int:
    return 1


def blockchain_sort_fn(current_event: WrappedEvent, new_event: WrappedEvent) -> int:
    if current_event.slot == new_event.slot:
        return -1 if current_event.tx_sig_index < new_event.tx_sig_index else 1

    return -1 if current_event.slot <= new_event.slot else 1


def get_sort_fn(
    order_by: EventSubscriptionOrderBy, order_dir: EventSubscriptionOrderDirection
) -> SortFn:
    if order_by == "client":
        return client_sort_asc_fn if order_dir == "asc" else client_sort_desc_fn

    return blockchain_sort_fn
