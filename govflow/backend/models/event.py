import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from backend.models.enums import EventType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


class Event(BaseModel):
    event_id: str = Field(default_factory=_new_id)
    workflow_id: str
    event_type: EventType
    payload: Dict[str, Any] = Field(default_factory=dict)
    source_agent: str = "system"
    timestamp: datetime = Field(default_factory=_utcnow)
    correlation_id: Optional[str] = None
