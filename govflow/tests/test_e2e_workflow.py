import pytest

from backend.agents.schemas import EligibilityResult, GoalAnalysis, ServicePlan
from backend.models.enums import EventType, WorkflowStatus
from backend.models.event import Event

GOAL = (
    "I want to start a small food-processing business making packaged snacks "
    "in a rented commercial unit, with 4 employees and about 1,200,000 Demo "
    "Currency Units expected annual turnover."
)

EXPECTED_AGENTS = {
    "GoalInterpreterAgent",
    "RegulationAgent",
    "WorkflowPlannerAgent",
    "EligibilityAgent",
    "DocumentAgent",
    "DepartmentRouterAgent",
    "ApplicationAgent",
    "StatusMonitorAgent",
    "NotificationAgent",
}


def _configure_happy_path_stub(stub, *, extracted_entities=None):
    stub.set_response(
        GoalAnalysis,
        GoalAnalysis(
            goal=GOAL,
            location="Demo Municipality commercial district",
            business_type="food_processing",
            required_workflow=True,
            extracted_entities=extracted_entities or {"business_name": "Sunrise Snacks Co"},
            missing_info=[],
        ),
    )
    stub.set_response(
        ServicePlan,
        ServicePlan(
            services=["business_registration", "tax_registration", "food_license", "local_approval"],
            dependencies={
                "business_registration": [],
                "tax_registration": ["business_registration"],
                "food_license": ["business_registration"],
                "local_approval": ["tax_registration", "food_license"],
            },
            reasoning="Food processing business with a physical premises needs all four services.",
        ),
    )
    stub.set_response(
        EligibilityResult,
        EligibilityResult(status="eligible", missing_fields=[], reasoning="Meets all stated eligibility rules."),
    )


@pytest.mark.asyncio
async def test_full_autonomous_cascade_reaches_completed(wired_system):
    _configure_happy_path_stub(wired_system.stub)

    workflow_id = await wired_system.engine.submit_user_goal(user_id="demo-user", goal=GOAL)
    went_idle = await wired_system.agents.status_monitor.wait_until_idle(timeout=25)
    assert went_idle, "polling never settled -- autonomous cascade did not finish"

    workflow = wired_system.workflow_repo.get(workflow_id)
    assert workflow.status == WorkflowStatus.COMPLETED
    assert set(workflow.completed_steps) == {
        "business_registration",
        "tax_registration",
        "food_license",
        "local_approval",
    }
    assert workflow.failed_steps == []
    assert len(workflow.applications) == 4

    audit_entries = wired_system.audit_repo.list_for_workflow(workflow_id)
    agents_seen = {e.agent for e in audit_entries if e.source != "bus_wide_audit_listener"}
    assert EXPECTED_AGENTS <= agents_seen, f"missing agents in audit trail: {EXPECTED_AGENTS - agents_seen}"

    # AuditAgent's bus-wide safety net fired for every event, independent
    # of each agent's own self.audit() call.
    bus_wide_entries = [e for e in audit_entries if e.source == "bus_wide_audit_listener"]
    assert len(bus_wide_entries) >= 15

    notifications = wired_system.notification_repo.list_for_workflow(workflow_id)
    assert len(notifications) > 0
    assert any("complete" in n.message.lower() for n in notifications)


@pytest.mark.asyncio
async def test_rejection_opens_hitl_gate_and_stops_autonomous_progression(wired_system):
    _configure_happy_path_stub(
        wired_system.stub, extracted_entities={"business_name": "Test Co", "scenario": "rejected"}
    )

    workflow_id = await wired_system.engine.submit_user_goal(user_id="demo-user", goal=GOAL)
    await wired_system.agents.status_monitor.wait_until_idle(timeout=25)

    workflow = wired_system.workflow_repo.get(workflow_id)
    # business_registration was rejected -> BLOCKED, not FAILED (recoverable
    # via human review) -- and nothing downstream should have been
    # submitted, since business_registration is a prerequisite for every
    # other step.
    assert workflow.status == WorkflowStatus.BLOCKED
    assert len(workflow.applications) == 1
    assert workflow.applications[0]["service"] == "business-registration"

    events = wired_system.event_repo.list_for_workflow(workflow_id)
    assert any(e.event_type == EventType.APPLICATION_REJECTED for e in events)
    assert any(e.event_type == EventType.USER_ACTION_REQUIRED for e in events)


@pytest.mark.asyncio
async def test_workflow_resumed_abandon_action_permanently_fails_step(wired_system):
    _configure_happy_path_stub(
        wired_system.stub, extracted_entities={"business_name": "Test Co", "scenario": "rejected"}
    )

    workflow_id = await wired_system.engine.submit_user_goal(user_id="demo-user", goal=GOAL)
    await wired_system.agents.status_monitor.wait_until_idle(timeout=25)
    workflow = wired_system.workflow_repo.get(workflow_id)
    assert workflow.status == WorkflowStatus.BLOCKED

    resume_event = Event(
        workflow_id=workflow_id,
        event_type=EventType.WORKFLOW_RESUMED,
        payload={"step_id": "business_registration", "action": "abandon"},
        source_agent="test",
    )
    await wired_system.bus.publish(resume_event)

    workflow = wired_system.workflow_repo.get(workflow_id)
    assert workflow.status == WorkflowStatus.FAILED
    assert "business_registration" in workflow.failed_steps
