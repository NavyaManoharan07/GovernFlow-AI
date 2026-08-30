"""Notification model.

Added in Part 2 so NotificationAgent has somewhere real to persist
human-readable notifications. Part 3 will stream these over WebSocket;
Part 2 only needs them queryable (e.g. for a future GET route and for
tests asserting the agent actually ran).
"""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from backend.models.enums import EventType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Notification(BaseModel):
    notification_id: str
    workflow_id: str
    event_type: EventType
    message: str
    severity: str = "info"  # info | warning | error
    created_at: datetime = Field(default_factory=_utcnow)
    read: bool = False
