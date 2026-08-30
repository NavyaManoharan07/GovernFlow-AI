"""Event bus abstraction.

InProcessEventBus is the fully-working local implementation (asyncio-based).
PubSubEventBus is a structural stub for Google Cloud Pub/Sub, wired to the
same interface so Part 2/3 code doesn't need to change when cloud mode is
enabled later.
"""

from __future__ import annotations

import abc
import asyncio
import logging
import os
from collections import defaultdict
from typing import Awaitable, Callable, Dict, List

from backend.models.event import Event
from backend.models.enums import EventType

logger = logging.getLogger("govflow.events.bus")

EventHandler = Callable[[Event], Awaitable[None]]


class EventBus(abc.ABC):
    """Abstract interface every event bus implementation must satisfy."""

    @abc.abstractmethod
    async def publish(self, event: Event) -> None:
        """Publish an event to the bus."""
        raise NotImplementedError

    @abc.abstractmethod
    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a handler for a specific event type."""
        raise NotImplementedError

    @abc.abstractmethod
    def subscribe_all(self, handler: EventHandler) -> None:
        """Register a handler that fires for every event type."""
        raise NotImplementedError


class InProcessEventBus(EventBus):
    """A local, fully-working event bus backed by asyncio.

    Handlers are dispatched concurrently via ``asyncio.create_task`` so
    publish() does not block on handler execution. Each handler is wrapped
    by the retry mechanism (backend.events.retry) by the caller registering
    it -- the bus itself has no retry logic, it just fans events out.
    """

    def __init__(self) -> None:
        self._handlers: Dict[EventType, List[EventHandler]] = defaultdict(list)
        self._wildcard_handlers: List[EventHandler] = []
        self._history: List[Event] = []

    async def publish(self, event: Event) -> None:
        self._history.append(event)
        logger.info(
            "event published: type=%s workflow_id=%s source=%s",
            event.event_type,
            event.workflow_id,
            event.source_agent,
        )
        handlers = list(self._handlers.get(event.event_type, [])) + list(self._wildcard_handlers)
        if not handlers:
            logger.debug("no handlers registered for event_type=%s", event.event_type)
            return

        tasks = [asyncio.create_task(self._run_handler(handler, event)) for handler in handlers]
        await asyncio.gather(*tasks)

    async def _run_handler(self, handler: EventHandler, event: Event) -> None:
        try:
            await handler(event)
        except Exception:
            logger.exception(
                "unhandled exception in event handler %s for event_type=%s",
                getattr(handler, "__name__", repr(handler)),
                event.event_type,
            )

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)
        logger.debug("handler %s subscribed to %s", getattr(handler, "__name__", handler), event_type)

    def subscribe_all(self, handler: EventHandler) -> None:
        self._wildcard_handlers.append(handler)
        logger.debug("handler %s subscribed to all events", getattr(handler, "__name__", handler))

    @property
    def history(self) -> List[Event]:
        return list(self._history)


class PubSubEventBus(EventBus):
    """Structural stub for Google Cloud Pub/Sub.

    Not implemented in Part 1. Raises loudly if selected without being
    configured/implemented -- it must never silently no-op.
    """

    def __init__(self) -> None:
        self._project = os.environ.get("GOOGLE_CLOUD_PROJECT")

    def _not_implemented(self) -> NotImplementedError:
        return NotImplementedError(
            "PubSubEventBus is not implemented yet. To use Google Cloud Pub/Sub, "
            "set GOOGLE_CLOUD_PROJECT and implement backend.events.bus.PubSubEventBus "
            "(Part 2+). For local development, set EVENT_BUS_MODE=local instead."
        )

    async def publish(self, event: Event) -> None:
        raise self._not_implemented()

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        raise self._not_implemented()

    def subscribe_all(self, handler: EventHandler) -> None:
        raise self._not_implemented()


_singleton_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Factory returning the configured EventBus implementation.

    Reads EVENT_BUS_MODE=local|pubsub (defaults to local). The returned
    instance is a process-wide singleton so all publishers/subscribers
    share the same bus.
    """
    global _singleton_bus
    if _singleton_bus is not None:
        return _singleton_bus

    mode = os.environ.get("EVENT_BUS_MODE", "local").strip().lower()
    if mode == "local":
        _singleton_bus = InProcessEventBus()
    elif mode == "pubsub":
        _singleton_bus = PubSubEventBus()
    else:
        raise ValueError(f"Unknown EVENT_BUS_MODE={mode!r}. Expected 'local' or 'pubsub'.")

    logger.info("event bus initialized: mode=%s impl=%s", mode, type(_singleton_bus).__name__)
    return _singleton_bus


def reset_event_bus() -> None:
    """Test helper: clears the singleton so a fresh bus is created next call."""
    global _singleton_bus
    _singleton_bus = None
