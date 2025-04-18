from typing import Optional

from anchorpy import EventParser, Program
from events import Events as EventEmitter
from solana.rpc.async_api import AsyncClient
from solders.signature import Signature

from driftpy.events.event_list import EventList
from driftpy.events.parse import parse_logs
from driftpy.events.sort import get_sort_fn
from driftpy.events.tx_event_cache import TxEventCache
from driftpy.events.types import EventSubscriptionOptions, EventType, WrappedEvent


class EventSubscriber:
    def __init__(
        self,
        connection: AsyncClient,
        program: Program,
        options: EventSubscriptionOptions = EventSubscriptionOptions.default(),
    ):
        self.connection = connection
        self.program = program
        self.options = options
        self.subscribed = False
        self.event_list_map: dict[EventType:EventList] = {}
        for event_type in self.options.event_types:
            self.event_list_map[event_type] = EventList(
                self.options.max_events_per_type,
                get_sort_fn(self.options.order_by, self.options.order_dir),
                self.options.order_dir,
            )
        self.event_parser = EventParser(self.program.program_id, self.program.coder)
        self.log_provider = self.options.get_log_provider(connection)
        self.tx_event_cache = TxEventCache(self.options.max_tx)
        self.event_emitter = EventEmitter(("new_event",))

    def subscribe(self):
        self.log_provider.subscribe(self.handle_tx_logs)
        self.subscribed = True

    def unsubscribe(self):
        self.log_provider.unsubscribe()
        self.subscribed = False

    def handle_tx_logs(
        self,
        tx_sig: Signature,
        slot: int,
        logs: list[str],
    ):
        if self.tx_event_cache.has(str(tx_sig)):
            return

        wrapped_events = self.parse_events_from_logs(tx_sig, slot, logs)
        for wrapped_event in wrapped_events:
            self.event_list_map.get(wrapped_event.event_type).insert(wrapped_event)

        for wrapped_event in wrapped_events:
            self.event_emitter.new_event(wrapped_event)

        self.tx_event_cache.add(str(tx_sig), wrapped_events)

    def parse_events_from_logs(self, tx_sig: Signature, slot: int, logs: list[str]):
        wrapped_events = []

        events = parse_logs(self.program, logs)

        for index, event in enumerate(events):
            if event.name in self.event_list_map:
                wrapped_event = WrappedEvent(
                    event_type=event.name,
                    tx_sig=tx_sig,
                    slot=slot,
                    tx_sig_index=index,
                    data=event.data,
                )
                wrapped_events.append(wrapped_event)

        return wrapped_events

    def get_event_list(self, event_type: EventType) -> Optional[EventList]:
        return self.event_list_map.get(event_type)

    def get_events_array(self, event_type: EventType) -> Optional[list[WrappedEvent]]:
        event_list = self.event_list_map.get(event_type)
        return None if event_list is None else event_list.to_array()

    def get_events_by_tx(self, tx_sig: str) -> Optional[list[WrappedEvent]]:
        return self.tx_event_cache.get(tx_sig)
