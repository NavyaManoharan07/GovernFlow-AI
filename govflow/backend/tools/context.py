"""Process-wide tool context: the repos + engine every tool needs.

Mirrors the pattern Part 1 already uses for the event bus
(backend.events.bus.get_event_bus) and persistence
(backend.services.factory.get_repositories): a single place that owns the
live instances, set once at startup, retrieved by name everywhere else.
Tools and agents run as event-bus handlers (not FastAPI request handlers),
so they can't rely on request-scoped dependency injection -- they need a
process-wide singleton instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.events.bus import EventBus
from backend.services.interfaces import AuditRepository, EventRepository, NotificationRepository, WorkflowRepository


@dataclass
class ToolContext:
    workflow_repo: WorkflowRepository
    event_repo: EventRepository
    audit_repo: AuditRepository
    notification_repo: NotificationRepository
    event_bus: EventBus
    engine: "object"  # backend.workflows.engine.WorkflowEngine -- typed loosely to avoid a circular import


_context: Optional[ToolContext] = None


def set_tool_context(context: ToolContext) -> None:
    global _context
    _context = context


def get_tool_context() -> ToolContext:
    if _context is None:
        raise RuntimeError(
            "Tool context not initialized. Call backend.tools.context.set_tool_context(...) "
            "during application startup before any tool is invoked."
        )
    return _context


def reset_tool_context() -> None:
    """Test helper."""
    global _context
    _context = None
