import time

from backend.agents.schemas import EligibilityResult, GoalAnalysis, ServicePlan
from backend.api.routes import DEMO_GOAL

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

# The minimum event sequence every successful 4-service demo run must
# contain, in this relative order (other events like APPLICATION_STATUS_CHANGED
# for the SUBMITTED->PENDING transition and repeated NEXT_ACTION_TRIGGERED /
# DOCUMENTS_VALIDATED / APPLICATION_READY / APPLICATION_SUBMITTED /
# APPLICATION_APPROVED cycles for the other 3 services are expected and
# fine between these anchors).
EXPECTED_ANCHOR_SEQUENCE = [
    "USER_REQUEST_CREATED",
    "GOAL_ANALYZED",
    "REQUIREMENTS_IDENTIFIED",
    "WORKFLOW_CREATED",
    "ELIGIBILITY_CHECKED",
    "NEXT_ACTION_TRIGGERED",
    "DOCUMENTS_VALIDATED",
    "APPLICATION_READY",
    "APPLICATION_SUBMITTED",
    "APPLICATION_APPROVED",
    "WORKFLOW_COMPLETED",
]


def _configure_full_demo_stub(stub, scenario_hint=None):
    entities = {"business_name": "TN Snacks Co"}
    if scenario_hint:
        entities["scenario"] = scenario_hint
    stub.set_response(
        GoalAnalysis,
        GoalAnalysis(
            goal=DEMO_GOAL,
            location="Tamil Nadu",
            business_type="food_processing",
            required_workflow=True,
            extracted_entities=entities,
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
            reasoning="Food processing business with physical premises needs all four catalog services.",
        ),
    )
    stub.set_response(EligibilityResult, EligibilityResult(status="eligible", missing_fields=[], reasoning="Meets all rules."))


def _poll_until_terminal(client, workflow_id, timeout=20):
    terminal = {"COMPLETED", "FAILED", "BLOCKED", "WAITING_FOR_USER"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/workflows/{workflow_id}")
        if r.status_code == 200 and r.json()["status"] in terminal:
            return r.json()
        time.sleep(0.05)
    raise TimeoutError(f"workflow {workflow_id} never reached a terminal state within {timeout}s")


def test_demo_run_full_happy_path_event_sequence_and_audit_coverage(api_client):
    """POST /api/demo/run -> poll until COMPLETED -> assert the event
    history contains the full expected anchor sequence in order, and the
    audit trail has entries from every agent that should have
    participated."""
    _configure_full_demo_stub(api_client.stub)

    r = api_client.client.post("/api/demo/run", params={"scenario": "clean"})
    assert r.status_code == 202
    workflow_id = r.json()["workflow_id"]
    assert r.json()["goal"] == DEMO_GOAL

    workflow = _poll_until_terminal(api_client.client, workflow_id)
    assert workflow["status"] == "COMPLETED"
    assert set(workflow["completed_steps"]) == {
        "business_registration",
        "tax_registration",
        "food_license",
        "local_approval",
    }
    assert len(workflow["applications"]) == 4

    events = api_client.client.get(f"/api/workflows/{workflow_id}/events").json()
    event_types = [e["event_type"] for e in events]

    # Every anchor event type appears, and in the right relative order.
    indices = []
    for anchor in EXPECTED_ANCHOR_SEQUENCE:
        assert anchor in event_types, f"missing expected event type {anchor}"
        indices.append(event_types.index(anchor))
    assert indices == sorted(indices), "anchor events were out of order"

    # APPLICATION_APPROVED should appear 4 times (once per service).
    assert event_types.count("APPLICATION_APPROVED") == 4
    assert event_types.count("APPLICATION_SUBMITTED") == 4

    audit = api_client.client.get(f"/api/workflows/{workflow_id}/audit").json()
    agents_seen = {a["agent"] for a in audit if a["source"] != "bus_wide_audit_listener"}
    assert EXPECTED_AGENTS <= agents_seen, f"missing from audit trail: {EXPECTED_AGENTS - agents_seen}"

    bus_wide = [a for a in audit if a["source"] == "bus_wide_audit_listener"]
    assert len(bus_wide) >= len(events)  # AuditAgent logs at least one entry per event


def test_demo_run_rejected_scenario_lands_on_blocked_not_crash_or_complete(api_client):
    """The alternate failure-scenario flag (?scenario=rejected) must
    autonomously gate the workflow to BLOCKED, never crash the request and
    never silently report COMPLETED."""
    _configure_full_demo_stub(api_client.stub)

    r = api_client.client.post("/api/demo/run", params={"scenario": "rejected"})
    assert r.status_code == 202
    workflow_id = r.json()["workflow_id"]

    workflow = _poll_until_terminal(api_client.client, workflow_id)
    assert workflow["status"] == "BLOCKED"
    assert workflow["status"] != "COMPLETED"
    # Only business_registration should have been attempted -- rejection on
    # the very first (root) step must stop everything downstream.
    assert len(workflow["applications"]) == 1
    assert workflow["applications"][0]["service"] == "business-registration"

    events = api_client.client.get(f"/api/workflows/{workflow_id}/events").json()
    event_types = [e["event_type"] for e in events]
    assert "APPLICATION_REJECTED" in event_types
    assert "USER_ACTION_REQUIRED" in event_types
    assert "WORKFLOW_COMPLETED" not in event_types

    # NotificationAgent must have surfaced this (queryable via the audit
    # trail, per Part 3's design -- no dedicated notifications endpoint).
    audit = api_client.client.get(f"/api/workflows/{workflow_id}/audit").json()
    notification_entries = [a for a in audit if a["agent"] == "NotificationAgent"]
    assert any("rejected" in a["decision"].lower() for a in notification_entries)


def test_demo_run_document_missing_scenario_lands_on_waiting_for_user(api_client):
    _configure_full_demo_stub(api_client.stub)

    r = api_client.client.post("/api/demo/run", params={"scenario": "document_missing"})
    assert r.status_code == 202
    workflow_id = r.json()["workflow_id"]

    workflow = _poll_until_terminal(api_client.client, workflow_id)
    assert workflow["status"] == "WAITING_FOR_USER"
    assert workflow["status"] != "COMPLETED"

    events = api_client.client.get(f"/api/workflows/{workflow_id}/events").json()
    event_types = [e["event_type"] for e in events]
    assert "DOCUMENT_MISSING" in event_types
