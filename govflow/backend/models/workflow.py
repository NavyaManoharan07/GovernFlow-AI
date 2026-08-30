from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.models.enums import StepStatus, WorkflowStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowStep(BaseModel):
    id: str
    name: str
    service: str
    depends_on: List[str] = Field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Workflow(BaseModel):
    workflow_id: str
    user_id: str
    goal: str
    status: WorkflowStatus = WorkflowStatus.RUNNING
    current_step: Optional[str] = None
    completed_steps: List[str] = Field(default_factory=list)
    pending_steps: List[str] = Field(default_factory=list)
    failed_steps: List[str] = Field(default_factory=list)
    required_documents: List[Dict[str, Any]] = Field(default_factory=list)
    applications: List[Dict[str, Any]] = Field(default_factory=list)
    events: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    # Added in Part 3: free-form, caller-supplied metadata that survives the
    # whole event chain. Used by the demo orchestrator to force a
    # deterministic mock-API scenario (metadata["scenario"]) regardless of
    # what Gemini's free-form extracted_entities happens to contain, so the
    # judged demo path never depends on LLM variability. Defaults to {} so
    # existing persisted rows without this key still deserialize fine.
    metadata: Dict[str, Any] = Field(default_factory=dict)
