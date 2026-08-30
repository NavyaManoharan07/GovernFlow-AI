from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditLogEntry(BaseModel):
    """Records a single decision/action for traceability.

    Part 2/3 agents write these; the schema and persistence method are
    defined now so the seam is ready.
    """

    timestamp: datetime = Field(default_factory=_utcnow)
    workflow_id: str
    event: str
    agent: str
    decision: str
    source: str
    tool: Optional[str] = None
    api_result: Optional[Dict[str, Any]] = None
    state_transition: Optional[Dict[str, Any]] = None
