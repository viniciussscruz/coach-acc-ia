from __future__ import annotations

from collections import defaultdict
from typing import Callable, DefaultDict, Dict, List

from ai_driving_coach.core.events import Event

EventHandler = Callable[[Event], None]


class EventBus:
    """In-process pub/sub for telemetry pipeline events."""

    def __init__(self) -> None:
        self._handlers: DefaultDict[str, List[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._handlers[event_name].append(handler)

    def publish(self, event: Event) -> None:
        for handler in self._handlers[event.name]:
            handler(event)

    def subscriber_count(self) -> Dict[str, int]:
        return {event_name: len(handlers) for event_name, handlers in self._handlers.items()}

