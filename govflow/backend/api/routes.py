"""Full REST API surface for GovFlow AI (Part 3).

Route list:
  GET  /health
  GET  /api/dashboard/summary                   -- aggregate stats across all workflows
  POST /api/workflows                          -- create + kick off async agent chain
  GET  /api/workflows/{workflow_id}             -- current Workflow state
  POST /api/workflows/{workflow_id}/events      -- manually publish an event (resume gate)
  GET  /api/workflows/{workflow_id}/events      -- event history
  GET  /api/workflows/{workflow_id}/audit       -- audit trail
  GET  /api/agents                              -- live agent registry
  GET  /api/services                            -- service catalog
  POST /api/demo/run                            -- deterministic demo scenario

Design notes (see backend/api/schemas.py and Step Zero investigation for
the full reasoning):
  - POST /api/workflows and POST /api/demo/run return 202 Accepted with
    just a workflow_id (WorkflowAcceptedResponse), not a full Workflow --
    no Workflow row exists yet at that point in Part 2's architecture
    (WorkflowPlannerAgent creates it a few hops later). They use
    WorkflowEngine.start_user_goal_async (Part 3 addition) so the HTTP
    response never blocks on the agent chain, per spec.
  - GET /api/workflows/{id} 404s if the row doesn't exist yet (it's a
    singular resource). GET .../events and .../audit never 404 -- they're
    append-only sub-resource collections keyed by workflow_id, and an
    empty list is the correct "nothing yet" response for a workflow_id
    that was just issued and is still processing asynchronously.
"""

from __future__ import annotations

import logging
import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.agents.catalog import ServiceInfo, get_service_catalog
from backend.agents import registry as agent_registry
from backend.api.auth import require_api_key
from backend.api.rate_limit import enforce_rate_limit
from backend.api.schemas import (
    ALLOWED_MANUAL_EVENT_TYPES,
    CreateWorkflowRequest,
    DashboardSummaryResponse,
    ManualEventRequest,
    RecentWorkflowSummary,
    WorkflowAcceptedResponse,
    WorkflowGraphResponse,
    WorkflowResumedPayload,
)
from backend.models.agent import AgentInfo
from backend.models.audit import AuditLogEntry
from backend.models.enums import WorkflowStatus
from backend.models.event import Event
from backend.models.workflow import Workflow, WorkflowStep

RECENT_WORKFLOWS_LIMIT = 10

logger = logging.getLogger("govflow.api.routes")

router = APIRouter()

DEMO_GOAL = "I want to start a small food-processing business in Tamil Nadu"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health")
async def health(request: Request) -> dict:
    return {
        "status": "ok",
        "service": "govflow-backend",
        "event_bus_mode": os.environ.get("EVENT_BUS_MODE", "local"),
        "persistence_mode": os.environ.get("PERSISTENCE_MODE", "local"),
    }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/api/dashboard/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(request: Request) -> DashboardSummaryResponse:
    """Aggregate stats across every workflow, for the Dashboard landing
    page. Everything here is computed fresh from persistence on every
    call -- WorkflowRepository.list() (already existed, just never had a
    route in front of it) and AuditRepository.count_all() (added
    alongside this route) -- there is no cached/precomputed total
    anywhere, so a workflow appearing or changing status shows up here on
    the next request."""
    workflow_repo = request.app.state.workflow_repo
    audit_repo = request.app.state.audit_repo

    workflows = workflow_repo.list()

    by_status = {status.value: 0 for status in WorkflowStatus}
    total_applications_submitted = 0
    for workflow in workflows:
        by_status[workflow.status.value] = by_status.get(workflow.status.value, 0) + 1
        total_applications_submitted += len(workflow.applications)

    most_recent = sorted(workflows, key=lambda w: w.updated_at, reverse=True)[:RECENT_WORKFLOWS_LIMIT]
    recent_workflows = [
        RecentWorkflowSummary(
            workflow_id=w.workflow_id, goal=w.goal, status=w.status.value, updated_at=w.updated_at
        )
        for w in most_recent
    ]

    return DashboardSummaryResponse(
        total_workflows=len(workflows),
        by_status=by_status,
        recent_workflows=recent_workflows,
        total_applications_submitted=total_applications_submitted,
        total_audit_entries=audit_repo.count_all(),
    )


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------


@router.post(
    "/api/workflows",
    response_model=WorkflowAcceptedResponse,
    status_code=202,
    dependencies=[Depends(require_api_key), Depends(enforce_rate_limit)],
)
async def create_workflow(body: CreateWorkflowRequest, request: Request) -> WorkflowAcceptedResponse:
    engine = request.app.state.workflow_engine
    workflow_id = engine.start_user_goal_async(user_id=body.user_id, goal=body.goal)
    return WorkflowAcceptedResponse(workflow_id=workflow_id, user_id=body.user_id, goal=body.goal)


@router.get("/api/workflows/{workflow_id}", response_model=Workflow)
async def get_workflow(workflow_id: str, request: Request) -> Workflow:
    workflow_repo = request.app.state.workflow_repo
    workflow = workflow_repo.get(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail=f"workflow {workflow_id!r} not found")
    return workflow


@router.post(
    "/api/workflows/{workflow_id}/events",
    response_model=Event,
    status_code=202,
    dependencies=[Depends(require_api_key)],
)
async def publish_manual_event(workflow_id: str, body: ManualEventRequest, request: Request) -> Event:
    workflow_repo = request.app.state.workflow_repo
    workflow = workflow_repo.get(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail=f"workflow {workflow_id!r} not found")

    if body.event_type not in ALLOWED_MANUAL_EVENT_TYPES:
        allowed = sorted(t.value for t in ALLOWED_MANUAL_EVENT_TYPES)
        raise HTTPException(
            status_code=422,
            detail=f"event_type {body.event_type.value!r} cannot be published manually. Allowed: {allowed}",
        )

    try:
        validated_payload = WorkflowResumedPayload.model_validate(body.payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"invalid payload for {body.event_type.value}: {exc}") from exc

    event_bus = request.app.state.event_bus
    event_repo = request.app.state.event_repo
    event = Event(
        workflow_id=workflow_id,
        event_type=body.event_type,
        payload=validated_payload.model_dump(),
        source_agent="api_user_action",
    )
    event_repo.append(event)
    await event_bus.publish(event)
    return event


@router.get("/api/workflows/{workflow_id}/events", response_model=List[Event])
async def list_workflow_events(workflow_id: str, request: Request) -> List[Event]:
    event_repo = request.app.state.event_repo
    return event_repo.list_for_workflow(workflow_id)


@router.get("/api/workflows/{workflow_id}/audit", response_model=List[AuditLogEntry])
async def list_workflow_audit(workflow_id: str, request: Request) -> List[AuditLogEntry]:
    audit_repo = request.app.state.audit_repo
    return audit_repo.list_for_workflow(workflow_id)


@router.get("/api/workflows/{workflow_id}/graph", response_model=WorkflowGraphResponse)
async def get_workflow_graph(workflow_id: str, request: Request) -> WorkflowGraphResponse:
    engine = request.app.state.workflow_engine
    if not engine.has_graph(workflow_id):
        return WorkflowGraphResponse(workflow_id=workflow_id, available=False, steps=[])
    graph = engine.get_graph(workflow_id)
    return WorkflowGraphResponse(workflow_id=workflow_id, available=True, steps=graph.all_steps())


# ---------------------------------------------------------------------------
# Agents + services
# ---------------------------------------------------------------------------


@router.get("/api/agents", response_model=List[AgentInfo])
async def list_agents() -> List[AgentInfo]:
    return agent_registry.get_all()


@router.get("/api/services", response_model=List[ServiceInfo])
async def list_services() -> List[ServiceInfo]:
    return get_service_catalog()


# ---------------------------------------------------------------------------
# Demo orchestration
# ---------------------------------------------------------------------------


@router.post(
    "/api/demo/run",
    response_model=WorkflowAcceptedResponse,
    status_code=202,
    dependencies=[Depends(require_api_key), Depends(enforce_rate_limit)],
)
async def run_demo(request: Request, scenario: str = "clean", user_id: str = "demo-user") -> WorkflowAcceptedResponse:
    """Triggers the deterministic demo scenario.

    ?scenario=clean (default): drives every mock application through the
    clean approval path -- the real agent chain runs end to end
    (Goal Interpreter -> Regulation/RAG -> Workflow Planner -> Eligibility
    -> Document checklist -> Department Router -> Application submission ->
    Status Monitor polling -> next-step detection -> repeat -> COMPLETED).

    ?scenario=document_missing or ?scenario=rejected: forces every mock
    application submission down that path instead (via
    Workflow.metadata["scenario"], which ApplicationAgent checks before
    Gemini's own free-form extraction -- see backend/agents/application.py),
    demonstrating autonomous failure handling: StatusMonitorAgent detects
    it, the workflow gates to WAITING_FOR_USER/BLOCKED via
    WorkflowEngine.block_step, and NotificationAgent surfaces it. The goal
    string and every "soft" reasoning step (interpretation, planning,
    eligibility) still run for real via Gemini -- only the mock government
    API outcome is forced, which is the actual reliability-critical part
    for a live demo.
    """
    valid_scenarios = {"clean", "document_missing", "rejected"}
    if scenario not in valid_scenarios:
        raise HTTPException(status_code=422, detail=f"scenario must be one of {sorted(valid_scenarios)}")

    engine = request.app.state.workflow_engine
    metadata = {"scenario": scenario, "demo": True}
    workflow_id = engine.start_user_goal_async(user_id=user_id, goal=DEMO_GOAL, metadata=metadata)
    return WorkflowAcceptedResponse(
        workflow_id=workflow_id,
        user_id=user_id,
        goal=DEMO_GOAL,
        message=f"Demo started (scenario={scenario}). Connect to WS /ws/workflows/{workflow_id} to watch it unfold.",
    )
