from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from backend.models.enums import ApplicationStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Application(BaseModel):
    application_id: str
    workflow_id: str
    service: str
    department: str
    status: ApplicationStatus = ApplicationStatus.SUBMITTED
    submitted_at: datetime = Field(default_factory=_utcnow)
    payload: Dict[str, Any] = Field(default_factory=dict)
    response: Optional[Dict[str, Any]] = None
    retry_count: int = 0
