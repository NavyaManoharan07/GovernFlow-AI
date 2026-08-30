"""Declarative handler registry.

Maps EventType -> list of handler callables. Part 2 agents register
themselves here (via register_handler) instead of modifying the event bus
or the workflow engine directly. wire_registry_to_bus() then subscribes
every registered handler onto a live EventBus, wrapping each with retry
logic.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Optional

from backend.events.bus import EventBus, EventHandler
from backend.events.retry import with_retry
from backend.models.enums import EventType
from backend.models.event import Event
from backend.services.interfaces import EventRepository

logger = logging.getLogger("govflow.events.registry")

_registry: Dict[EventType, List[EventHandler]] = defaultdict(list)
# Added in Part 2: handlers that must see every event regardless of type
# (e.g. AuditAgent's bus-wide safety net). Kept separate from _registry so
# get_registered_handlers() stays unambiguous about per-type subscriptions.
_wildcard_registry: List[EventHandler] = []


def register_handler(event_type: EventType, handler: EventHandler) -> None:
    """Declaratively register a handler for an event type.

    Safe to call at import time from agent modules (Part 2) -- it does not
    require a live event bus.
    """
    _registry[event_type].append(handler)
    logger.debug("registered handler %s for %s", getattr(handler, "__name__", handler), event_type)


def register_wildcard_handler(handler: EventHandler) -> None:
    """Declaratively register a handler that fires for every event type."""
    _wildcard_registry.append(handler)
    logger.debug("registered wildcard handler %s", getattr(handler, "__name__", handler))


def get_registered_handlers() -> Dict[EventType, List[EventHandler]]:
    return {k: list(v) for k, v in _registry.items()}


def get_registered_wildcard_handlers() -> List[EventHandler]:
    return list(_wildcard_registry)


def clear_registry() -> None:
    """Test helper: clears all registered handlers, including wildcard ones."""
    _registry.clear()
    _wildcard_registry.clear()


def wire_registry_to_bus(bus: EventBus, *, use_retry: bool = True, event_repo: Optional[EventRepository] = None) -> None:
    """Subscribe every registered handler onto the given bus.

    Each handler is wrapped with retry + failure-event publishing so a
    single flaky handler cannot silently break the workflow.

    ``event_repo``, added in Part 3: without it, a WORKFLOW_FAILED event
    from exhausted retries is only ever live-dispatched via
    ``bus.publish`` -- never persisted -- so it would be invisible to
    GET /api/workflows/{id}/events and to the WebSocket stream (which
    reads history from the repository to dedupe against concurrent
    connects, see backend/api/websocket.py). When provided, the failure
    event is appended to the repo before being published, exactly like
    WorkflowEngine._record_and_publish / Agent.publish already do for
    every other event. Optional (defaults to the old live-only behavior)
    so existing callers that don't have a repo handy still work.
    """

    def _make_failure_publisher():
        if event_repo is None:
            return bus.publish

        async def _persist_and_publish(evt: Event) -> None:
            event_repo.append(evt)
            await bus.publish(evt)

        return _persist_and_publish

    for event_type, handlers in _registry.items():
        for handler in handlers:
            if use_retry:
                bus.subscribe(event_type, with_retry(handler, publish_failure_event=_make_failure_publisher()))
            else:
                bus.subscribe(event_type, handler)
    for handler in _wildcard_registry:
        if use_retry:
            bus.subscribe_all(with_retry(handler, publish_failure_event=_make_failure_publisher()))
        else:
            bus.subscribe_all(handler)
    logger.info(
        "wired %d event types + %d wildcard handlers from registry onto bus (failure-event persistence=%s)",
        len(_registry),
        len(_wildcard_registry),
        event_repo is not None,
    )
