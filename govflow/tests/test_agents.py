import pytest

from backend.agents.application import ApplicationAgent
from backend.agents.audit import AuditAgent
from backend.agents.department_router import DepartmentRouterAgent
from backend.agents.document import DocumentAgent
from backend.agents.eligibility import EligibilityAgent
from backend.agents.goal_interpreter import GoalInterpreterAgent
from backend.agents.notification import NotificationAgent
from backend.agents.regulation import RegulationAgent
from backend.agents.schemas import EligibilityResult, GoalAnalysis, ServicePlan
from backend.agents.status_monitor import StatusMonitorAgent
from backend.agents.workflow_planner import WorkflowPlannerAgent
from backend.models.enums import EventType, StepStatus, WorkflowStatus
from backend.models.event import Event
from backend.tools.registry import invoke_tool


def _event(workflow_id, event_type, payload):
    return Event(workflow_id=workflow_id, event_type=event_type, payload=payload, source_agent="test")


# ---------------------------------------------------------------------------
# GoalInterpreterAgent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_goal_interpreter_produces_goal_analyzed_event(bare_context):
    agent = GoalInterpreterAgent(bare_context.stub)
    bare_context.stub.set_response(
        GoalAnalysis,
        GoalAnalysis(
            goal="start a food business",
            location="Demo City",
            business_type="food_processing",
            required_workflow=True,
            extracted_entities={"business_name": "Test Foods"},
            missing_info=[],
        ),
    )
    workflow_id = "wf-goal-1"
    event = _event(workflow_id, EventType.USER_REQUEST_CREATED, {"goal": "start a food business", "user_id": "u1"})

    await agent.run(event)

    events = bare_context.event_repo.list_for_workflow(workflow_id)
    goal_events = [e for e in events if e.event_type == EventType.GOAL_ANALYZED]
    assert len(goal_events) == 1
    assert goal_events[0].payload["business_type"] == "food_processing"
    assert goal_events[0].payload["required_workflow"] is True
    assert goal_events[0].payload["user_id"] == "u1"

    # Audit trail must reflect this agent actually ran.
    audit_entries = bare_context.audit_repo.list_for_workflow(workflow_id)
    assert any(e.agent == "GoalInterpreterAgent" for e in audit_entries)


@pytest.mark.asyncio
async def test_goal_interpreter_ignores_unrelated_event_types(bare_context):
    agent = GoalInterpreterAgent(bare_context.stub)  # no canned response registered
    event = _event("wf-goal-2", EventType.GOAL_ANALYZED, {"goal": "irrelevant"})
    await agent.run(event)  # must not attempt an LLM call and must not raise
    assert bare_context.event_repo.list_for_workflow("wf-goal-2") == []


# ---------------------------------------------------------------------------
# RegulationAgent (no LLM)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regulation_agent_retrieves_rules_for_every_catalog_service(bare_context):
    agent = RegulationAgent()
    workflow_id = "wf-reg-1"
    event = _event(
        workflow_id,
        EventType.GOAL_ANALYZED,
        {"goal": "start a food processing business", "business_type": "food_processing", "user_id": "u1"},
    )
    await agent.run(event)

    events = bare_context.event_repo.list_for_workflow(workflow_id)
    req_events = [e for e in events if e.event_type == EventType.REQUIREMENTS_IDENTIFIED]
    assert len(req_events) == 1
    rules_by_service = req_events[0].payload["rules_by_service"]
    assert set(rules_by_service.keys()) == {
        "business_registration",
        "tax_registration",
        "food_license",
        "local_approval",
    }
    assert any(rules_by_service.values())  # at least one service got real results
    assert req_events[0].payload["goal_analysis"]["user_id"] == "u1"


# ---------------------------------------------------------------------------
# WorkflowPlannerAgent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workflow_planner_creates_workflow_from_gemini_plan(bare_context):
    agent = WorkflowPlannerAgent(bare_context.stub)
    bare_context.stub.set_response(
        ServicePlan,
        ServicePlan(
            services=["business_registration", "food_license"],
            dependencies={"business_registration": [], "food_license": ["business_registration"]},
            reasoning="Food business needs registration and a food license.",
        ),
    )
    workflow_id = "wf-plan-1"
    event = _event(
        workflow_id,
        EventType.REQUIREMENTS_IDENTIFIED,
        {
            "rules_by_service": {"business_registration": [], "food_license": []},
            "goal_analysis": {"goal": "start a food business", "user_id": "u1", "required_workflow": True},
        },
    )

    await agent.run(event)

    workflow = bare_context.workflow_repo.get(workflow_id)
    assert workflow is not None
    assert set(workflow.pending_steps) | set(workflow.completed_steps) >= {"business_registration"}
    graph = bare_context.engine.get_graph(workflow_id)
    assert {s.id for s in graph.all_steps()} == {"business_registration", "food_license"}
    assert graph.get_step("food_license").depends_on == ["business_registration"]


@pytest.mark.asyncio
async def test_workflow_planner_falls_back_to_default_deps_on_invalid_cycle(bare_context):
    agent = WorkflowPlannerAgent(bare_context.stub)
    # Gemini proposes a cycle -- must not be allowed to drive real state.
    bare_context.stub.set_response(
        ServicePlan,
        ServicePlan(
            services=["business_registration", "tax_registration"],
            dependencies={
                "business_registration": ["tax_registration"],
                "tax_registration": ["business_registration"],
            },
            reasoning="(intentionally malformed for the test)",
        ),
    )
    workflow_id = "wf-plan-2"
    event = _event(
        workflow_id,
        EventType.REQUIREMENTS_IDENTIFIED,
        {"rules_by_service": {}, "goal_analysis": {"goal": "g", "user_id": "u1", "required_workflow": True}},
    )

    await agent.run(event)  # must not raise despite the cyclic input

    graph = bare_context.engine.get_graph(workflow_id)
    # Fell back to the known-good default: business_registration has no
    # prerequisites, tax_registration depends on it.
    assert graph.get_step("business_registration").depends_on == []
    assert graph.get_step("tax_registration").depends_on == ["business_registration"]


@pytest.mark.asyncio
async def test_workflow_planner_skips_creation_when_goal_does_not_require_workflow(bare_context):
    agent = WorkflowPlannerAgent(bare_context.stub)  # no ServicePlan response needed
    workflow_id = "wf-plan-3"
    event = _event(
        workflow_id,
        EventType.REQUIREMENTS_IDENTIFIED,
        {"rules_by_service": {}, "goal_analysis": {"goal": "what's the weather", "user_id": "u1", "required_workflow": False}},
    )
    await agent.run(event)
    assert bare_context.workflow_repo.get(workflow_id) is None


# ---------------------------------------------------------------------------
# EligibilityAgent
# ---------------------------------------------------------------------------


async def _seed_workflow_with_goal_analysis(bare_context, workflow_id, goal_payload):
    await bare_context.engine.create_workflow(user_id="u1", goal=goal_payload.get("goal", "g"), workflow_id=workflow_id)
    bare_context.event_repo.append(_event(workflow_id, EventType.GOAL_ANALYZED, goal_payload))


@pytest.mark.asyncio
async def test_eligibility_agent_eligible_lets_chain_continue(bare_context):
    agent = EligibilityAgent(bare_context.stub)
    workflow_id = "wf-elig-1"
    await _seed_workflow_with_goal_analysis(
        bare_context, workflow_id, {"goal": "start a food business", "user_id": "u1"}
    )
    bare_context.stub.set_response(
        EligibilityResult, EligibilityResult(status="eligible", missing_fields=[], reasoning="all good")
    )

    await agent.run(_event(workflow_id, EventType.WORKFLOW_CREATED, {"step_ids": []}))

    events = bare_context.event_repo.list_for_workflow(workflow_id)
    assert any(e.event_type == EventType.ELIGIBILITY_CHECKED for e in events)
    workflow = bare_context.workflow_repo.get(workflow_id)
    assert workflow.status == WorkflowStatus.RUNNING


@pytest.mark.asyncio
async def test_eligibility_agent_ineligible_blocks_workflow(bare_context):
    agent = EligibilityAgent(bare_context.stub)
    workflow_id = "wf-elig-2"
    await _seed_workflow_with_goal_analysis(
        bare_context, workflow_id, {"goal": "start a food business in a residential zone", "user_id": "u1"}
    )
    bare_context.stub.set_response(
        EligibilityResult,
        EligibilityResult(status="ineligible", missing_fields=[], reasoning="zoning does not permit this"),
    )

    await agent.run(_event(workflow_id, EventType.WORKFLOW_CREATED, {"step_ids": []}))

    workflow = bare_context.workflow_repo.get(workflow_id)
    assert workflow.status == WorkflowStatus.BLOCKED
    events = bare_context.event_repo.list_for_workflow(workflow_id)
    assert any(e.event_type == EventType.USER_ACTION_REQUIRED for e in events)


@pytest.mark.asyncio
async def test_eligibility_agent_needs_information_waits_for_user(bare_context):
    agent = EligibilityAgent(bare_context.stub)
    workflow_id = "wf-elig-3"
    await _seed_workflow_with_goal_analysis(bare_context, workflow_id, {"goal": "start a business", "user_id": "u1"})
    bare_context.stub.set_response(
        EligibilityResult,
        EligibilityResult(status="needs_information", missing_fields=["location"], reasoning="location unknown"),
    )

    await agent.run(_event(workflow_id, EventType.WORKFLOW_CREATED, {"step_ids": []}))

    workflow = bare_context.workflow_repo.get(workflow_id)
    assert workflow.status == WorkflowStatus.WAITING_FOR_USER


# ---------------------------------------------------------------------------
# DocumentAgent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_document_agent_valid_documents(bare_context):
    agent = DocumentAgent()
    workflow_id = "wf-doc-1"
    await bare_context.engine.create_workflow(user_id="u1", goal="g", workflow_id=workflow_id)

    await agent.run(_event(workflow_id, EventType.NEXT_ACTION_TRIGGERED, {"ready_steps": ["business_registration"]}))

    events = bare_context.event_repo.list_for_workflow(workflow_id)
    assert any(e.event_type == EventType.DOCUMENTS_VALIDATED for e in events)
    assert not any(e.event_type == EventType.DOCUMENT_MISSING for e in events)


@pytest.mark.asyncio
async def test_document_agent_missing_documents(bare_context):
    agent = DocumentAgent()
    workflow_id = "wf-doc-2"
    await bare_context.engine.create_workflow(user_id="u1", goal="g", workflow_id=workflow_id)
    bare_context.event_repo.append(
        _event(
            workflow_id,
            EventType.GOAL_ANALYZED,
            {"goal": "g", "user_id": "u1", "extracted_entities": {"scenario": "document_missing"}},
        )
    )

    await agent.run(_event(workflow_id, EventType.NEXT_ACTION_TRIGGERED, {"ready_steps": ["business_registration"]}))

    events = bare_context.event_repo.list_for_workflow(workflow_id)
    missing = [e for e in events if e.event_type == EventType.DOCUMENT_MISSING]
    assert len(missing) == 1
    assert missing[0].payload["step_id"] == "business_registration"


@pytest.mark.asyncio
async def test_document_agent_skips_when_workflow_gated(bare_context):
    agent = DocumentAgent()
    workflow_id = "wf-doc-3"
    await bare_context.engine.create_workflow(user_id="u1", goal="g", workflow_id=workflow_id)
    await bare_context.engine.block_workflow(workflow_id, reason="test gate", workflow_status=WorkflowStatus.BLOCKED)

    await agent.run(_event(workflow_id, EventType.NEXT_ACTION_TRIGGERED, {"ready_steps": ["business_registration"]}))

    events = bare_context.event_repo.list_for_workflow(workflow_id)
    assert not any(e.event_type in (EventType.DOCUMENTS_VALIDATED, EventType.DOCUMENT_MISSING) for e in events)


# ---------------------------------------------------------------------------
# DepartmentRouterAgent (no LLM)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_department_router_routes_to_correct_tool(bare_context):
    agent = DepartmentRouterAgent()
    workflow_id = "wf-route-1"
    await agent.run(
        _event(
            workflow_id,
            EventType.DOCUMENTS_VALIDATED,
            {"step_id": "food_license", "service": "food_license", "checklist": []},
        )
    )
    events = bare_context.event_repo.list_for_workflow(workflow_id)
    ready_events = [e for e in events if e.event_type == EventType.APPLICATION_READY]
    assert len(ready_events) == 1
    assert ready_events[0].payload["tool_name"] == "call_food_license_api"


# ---------------------------------------------------------------------------
# ApplicationAgent (no LLM)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_application_agent_submits_and_records_application(bare_context):
    agent = ApplicationAgent()
    workflow_id = "wf-app-1"
    await bare_context.engine.create_workflow(user_id="u1", goal="Sunrise Foods application", workflow_id=workflow_id)

    await agent.run(
        _event(
            workflow_id,
            EventType.APPLICATION_READY,
            {"step_id": "business_registration", "service": "business_registration", "tool_name": "call_business_registration_api"},
        )
    )

    events = bare_context.event_repo.list_for_workflow(workflow_id)
    submitted = [e for e in events if e.event_type == EventType.APPLICATION_SUBMITTED]
    assert len(submitted) == 1
    assert submitted[0].payload["application_id"]

    workflow = bare_context.workflow_repo.get(workflow_id)
    assert len(workflow.applications) == 1
    assert workflow.applications[0]["step_id"] == "business_registration"


# ---------------------------------------------------------------------------
# StatusMonitorAgent (no LLM, real asyncio polling)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_monitor_reaches_approved(bare_context):
    agent = StatusMonitorAgent()
    workflow_id = "wf-status-1"
    result = invoke_tool(
        "call_business_registration_api", {"business_name": "Test Co", "scenario": "clean"}, workflow_id=workflow_id
    )

    await agent.run(
        _event(
            workflow_id,
            EventType.APPLICATION_SUBMITTED,
            {"step_id": "business_registration", "application_id": result.application_id},
        )
    )
    went_idle = await agent.wait_until_idle(timeout=10)
    assert went_idle

    events = bare_context.event_repo.list_for_workflow(workflow_id)
    assert any(e.event_type == EventType.APPLICATION_APPROVED for e in events)


@pytest.mark.asyncio
async def test_status_monitor_reaches_rejected(bare_context):
    agent = StatusMonitorAgent()
    workflow_id = "wf-status-2"
    result = invoke_tool(
        "call_tax_registration_api", {"business_name": "Test Co", "scenario": "rejected"}, workflow_id=workflow_id
    )

    await agent.run(
        _event(
            workflow_id,
            EventType.APPLICATION_SUBMITTED,
            {"step_id": "tax_registration", "application_id": result.application_id},
        )
    )
    await agent.wait_until_idle(timeout=10)

    events = bare_context.event_repo.list_for_workflow(workflow_id)
    assert any(e.event_type == EventType.APPLICATION_REJECTED for e in events)


@pytest.mark.asyncio
async def test_status_monitor_reaches_document_missing(bare_context):
    agent = StatusMonitorAgent()
    workflow_id = "wf-status-3"
    result = invoke_tool(
        "call_food_license_api", {"business_name": "Test Co", "scenario": "document_missing"}, workflow_id=workflow_id
    )

    await agent.run(
        _event(
            workflow_id,
            EventType.APPLICATION_SUBMITTED,
            {"step_id": "food_license", "application_id": result.application_id},
        )
    )
    await agent.wait_until_idle(timeout=10)

    events = bare_context.event_repo.list_for_workflow(workflow_id)
    assert any(e.event_type == EventType.DOCUMENT_MISSING for e in events)


# ---------------------------------------------------------------------------
# NotificationAgent (no LLM)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notification_agent_persists_notification(bare_context):
    agent = NotificationAgent()
    workflow_id = "wf-notif-1"
    await agent.run(_event(workflow_id, EventType.WORKFLOW_COMPLETED, {}))

    notifications = bare_context.notification_repo.list_for_workflow(workflow_id)
    assert len(notifications) == 1
    assert notifications[0].severity == "info"
    assert "complete" in notifications[0].message.lower()


@pytest.mark.asyncio
async def test_notification_agent_marks_rejection_as_error_severity(bare_context):
    agent = NotificationAgent()
    workflow_id = "wf-notif-2"
    await agent.run(
        _event(workflow_id, EventType.APPLICATION_REJECTED, {"step_id": "food_license", "reason": "test rejection"})
    )
    notifications = bare_context.notification_repo.list_for_workflow(workflow_id)
    assert notifications[0].severity == "error"


@pytest.mark.asyncio
async def test_notification_agent_ignores_untemplated_event_types(bare_context):
    agent = NotificationAgent()
    workflow_id = "wf-notif-3"
    await agent.run(_event(workflow_id, EventType.USER_REQUEST_CREATED, {"goal": "g"}))
    assert bare_context.notification_repo.list_for_workflow(workflow_id) == []


# ---------------------------------------------------------------------------
# AuditAgent (bus-wide safety net)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_agent_logs_any_event(bare_context):
    agent = AuditAgent()
    workflow_id = "wf-audit-1"
    await agent.run(_event(workflow_id, EventType.GOAL_ANALYZED, {"goal": "g"}))

    entries = bare_context.audit_repo.list_for_workflow(workflow_id)
    assert len(entries) == 1
    assert entries[0].source == "bus_wide_audit_listener"
    assert entries[0].event == EventType.GOAL_ANALYZED.value
