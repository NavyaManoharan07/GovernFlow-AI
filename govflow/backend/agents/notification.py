"""NotificationAgent: produces a short human-readable notification per
event and persists it via NotificationRepository. No WebSocket streaming
here -- that's Part 3's job; Part 2 only needs these queryable."""

from __future__ import annotations

import uuid
from typing import Any, Callable, Dict

from backend.agents.base import Agent
from backend.models.enums import EventType
from backend.models.event import Event
from backend.models.notification import Notification
from backend.tools.context import get_tool_context

_MESSAGES: Dict[EventType, Callable[[Dict[str, Any]], str]] = {
    EventType.GOAL_ANALYZED: lambda p: f"Understood your goal: {p.get('goal', '')}",
    EventType.WORKFLOW_CREATED: lambda p: f"Created your workflow (steps: {', '.join(p.get('step_ids', [])) or 'n/a'}).",
    EventType.ELIGIBILITY_CHECKED: lambda p: f"Eligibility confirmed: {p.get('reasoning', '')}",
    EventType.DOCUMENTS_VALIDATED: lambda p: f"All required documents are on file for {p.get('service', 'this step')}.",
    EventType.DOCUMENT_MISSING: lambda p: f"Missing documents for {p.get('service', 'a step')}: {', '.join(p.get('missing_documents', [])) or 'see checklist'}.",
    EventType.APPLICATION_SUBMITTED: lambda p: f"Application submitted for {p.get('service', 'a step')} (ID {p.get('application_id', '?')}).",
    EventType.APPLICATION_STATUS_CHANGED: lambda p: f"Application {p.get('application_id', '?')} status is now {p.get('status', '?')}.",
    EventType.APPLICATION_APPROVED: lambda p: f"Your application for step '{p.get('step_id', '?')}' was approved.",
    EventType.APPLICATION_REJECTED: lambda p: f"Your application for step '{p.get('step_id', '?')}' was rejected: {p.get('reason', '')}",
    EventType.USER_ACTION_REQUIRED: lambda p: f"Action needed: {p.get('reason', 'please review your workflow')}",
    EventType.WORKFLOW_COMPLETED: lambda p: "Your workflow is complete -- every step has been approved.",
    EventType.WORKFLOW_FAILED: lambda p: f"Your workflow failed: {p.get('reason', 'see audit log for details')}",
    EventType.WORKFLOW_RESUMED: lambda p: "Your workflow has resumed.",
}

_SEVERITY = {
    EventType.WORKFLOW_FAILED: "error",
    EventType.APPLICATION_REJECTED: "error",
    EventType.DOCUMENT_MISSING: "warning",
    EventType.USER_ACTION_REQUIRED: "warning",
}


class NotificationAgent(Agent):
    def __init__(self) -> None:
        super().__init__("NotificationAgent", "Produces human-readable notifications for workflow events")

    async def handle(self, event: Event) -> None:
        template = _MESSAGES.get(event.event_type)
        if template is None:
            return

        message = template(event.payload)
        severity = _SEVERITY.get(event.event_type, "info")

        ctx = get_tool_context()
        notification = Notification(
            notification_id=str(uuid.uuid4()),
            workflow_id=event.workflow_id,
            event_type=event.event_type,
            message=message,
            severity=severity,
        )
        ctx.notification_repo.append(notification)

        self.audit(
            event.workflow_id,
            event="NOTIFICATION_SENT",
            decision=message,
            source="agent",
        )
