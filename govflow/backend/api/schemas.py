"""Request/response Pydantic models for the REST API.

Response models reuse the real backend models (Workflow, Event,
AuditLogEntry, AgentInfo) directly wherever the route just returns that
resource unchanged -- no shadow/duplicate DTOs that could drift from what
the backend actually persists.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from backend.models.enums import EventType
from backend.models.workflow import WorkflowStep


class CreateWorkflowRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=200)
    goal: str = Field(min_length=1, max_length=4000)


class WorkflowAcceptedResponse(BaseModel):
    """Returned by POST /api/workflows and POST /api/demo/run.

    Not a full Workflow object: at the moment this response is built, no
    Workflow row exists yet (GoalInterpreterAgent -> RegulationAgent ->
    WorkflowPlannerAgent haven't run) -- the row is created a few hops
    later by WorkflowPlannerAgent, using this same workflow_id. Returning
    202 Accepted + workflow_id is the standard pattern for "processing
    kicked off asynchronously, poll or subscribe for the result," which is
    exactly what's happening here. Poll GET /api/workflows/{workflow_id}
    (404 until the row exists) or connect to WS /ws/workflows/{workflow_id}
    (usable immediately) for live progress.
    """

    workflow_id: str
    status: Literal["ACCEPTED"] = "ACCEPTED"
    user_id: str
    goal: str
    message: str = "Goal received. Agent chain is processing asynchronously."


# Manual event publishing (POST /api/workflows/{id}/events) is deliberately
# restricted to event types it's safe for an external caller to inject.
# WORKFLOW_RESUMED is the practical case described in the brief (resuming a
# WAITING_FOR_USER/BLOCKED workflow, whether that's "user supplied missing
# info" or "human reviewed a rejection") -- publishing e.g. WORKFLOW_COMPLETED
# or APPLICATION_APPROVED manually would let a caller forge system-owned
# state transitions, so those are not allowed here.
ALLOWED_MANUAL_EVENT_TYPES = {EventType.WORKFLOW_RESUMED}


class WorkflowResumedPayload(BaseModel):
    """Structured schema for a WORKFLOW_RESUMED payload -- the same shape
    WorkflowEngine._on_workflow_resumed expects. step_id=None resumes a
    workflow-level gate (EligibilityAgent's block_workflow); a specific
    step_id resumes that step's gate (block_step, e.g. after a rejection)."""

    step_id: Optional[str] = None
    action: Literal["retry", "abandon"] = "retry"


class ManualEventRequest(BaseModel):
    event_type: EventType
    payload: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: str
    detail: str


class WorkflowGraphResponse(BaseModel):
    """GET /api/workflows/{id}/graph.

    Added in Part 4: the Workflow model itself only exposes flattened
    completed_steps/pending_steps/failed_steps ID lists -- the actual DAG
    (step names, service, depends_on edges, per-step status) only lives in
    WorkflowEngine's in-memory WorkflowGraph. The frontend's Workflow Graph
    component needs real dependency edges, not a flat list, so this
    exposes WorkflowGraph.all_steps() directly. available=False (with
    steps=[]) if the graph isn't in memory for this process (e.g. after a
    backend restart -- a known Part 1 limitation) rather than fabricating
    edges from the flat lists.
    """

    workflow_id: str
    available: bool
    steps: List[WorkflowStep] = Field(default_factory=list)


class RecentWorkflowSummary(BaseModel):
    """One row of GET /api/dashboard/summary's recent_workflows list --
    intentionally a small subset of Workflow's fields (just enough for a
    dashboard row + click-through), not the full object."""

    workflow_id: str
    goal: str
    status: str
    updated_at: datetime


class DashboardSummaryResponse(BaseModel):
    """GET /api/dashboard/summary.

    Every number here is computed from real persisted data at request
    time via WorkflowRepository.list() / AuditRepository.count_all() --
    see backend/api/routes.py:get_dashboard_summary. Nothing is cached or
    invented; a fresh workflow shows up here the moment
    WorkflowPlannerAgent persists its row.
    """

    total_workflows: int
    by_status: Dict[str, int]
    recent_workflows: List[RecentWorkflowSummary] = Field(default_factory=list)
    total_applications_submitted: int
    total_audit_entries: int
