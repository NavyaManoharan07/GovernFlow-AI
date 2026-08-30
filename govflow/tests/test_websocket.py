import time

from backend.agents.schemas import EligibilityResult, GoalAnalysis, ServicePlan

GOAL = "I want to start a small food-processing business in Tamil Nadu"


def _configure_single_step_stub(stub):
    stub.set_response(
        GoalAnalysis,
        GoalAnalysis(
            goal=GOAL,
            location="Tamil Nadu",
            business_type="food_processing",
            required_workflow=True,
            extracted_entities={"business_name": "TN Snacks Co"},
            missing_info=[],
        ),
    )
    stub.set_response(
        ServicePlan,
        ServicePlan(
            services=["business_registration"],
            dependencies={"business_registration": []},
            reasoning="single-step test",
        ),
    )
    stub.set_response(EligibilityResult, EligibilityResult(status="eligible", missing_fields=[], reasoning="ok"))


def _drain_until(ws, predicate, timeout=10):
    """Reads messages off the socket until predicate(msg) is True or the
    timeout elapses. Returns the list of all messages seen (including the
    matching one)."""
    deadline = time.time() + timeout
    messages = []
    while time.time() < deadline:
        msg = ws.receive_json()
        messages.append(msg)
        if predicate(msg):
            return messages
    raise TimeoutError(f"predicate never matched within {timeout}s; saw {len(messages)} messages")


def test_websocket_connect_then_workflow_events_arrive_in_order(api_client):
    _configure_single_step_stub(api_client.stub)
    r = api_client.client.post("/api/workflows", json={"user_id": "u1", "goal": GOAL})
    workflow_id = r.json()["workflow_id"]

    with api_client.client.websocket_connect(f"/ws/workflows/{workflow_id}") as ws:
        messages = _drain_until(
            ws,
            lambda m: m["type"] == "state_change" and m["payload"].get("status") == "COMPLETED",
            timeout=15,
        )

    types_seen = [m["type"] for m in messages]
    assert "event" in types_seen
    assert "agent_activity" in types_seen
    assert "audit" in types_seen
    assert "state_change" in types_seen

    # Envelope shape: every message has exactly {type, timestamp, payload}.
    for m in messages:
        assert set(m.keys()) == {"type", "timestamp", "payload"}
        assert m["type"] in {"event", "agent_activity", "state_change", "audit"}

    # Ordering: USER_REQUEST_CREATED's "event" message must come before
    # the terminal COMPLETED state_change.
    event_types_in_order = [
        m["payload"]["event_type"] for m in messages if m["type"] == "event"
    ]
    assert event_types_in_order[0] == "USER_REQUEST_CREATED"
    assert "WORKFLOW_COMPLETED" in event_types_in_order
    assert event_types_in_order.index("USER_REQUEST_CREATED") < event_types_in_order.index("WORKFLOW_COMPLETED")


def test_websocket_snapshot_replays_history_for_late_connection(api_client):
    """A client connecting AFTER the workflow already progressed should
    still receive the full history as its initial snapshot, not just
    whatever happens next."""
    _configure_single_step_stub(api_client.stub)
    r = api_client.client.post("/api/workflows", json={"user_id": "u1", "goal": GOAL})
    workflow_id = r.json()["workflow_id"]

    # Wait for it to fully complete BEFORE connecting at all.
    deadline = time.time() + 10
    while time.time() < deadline:
        wf = api_client.client.get(f"/api/workflows/{workflow_id}").json()
        if wf.get("status") == "COMPLETED":
            break
        time.sleep(0.05)
    assert wf["status"] == "COMPLETED"

    with api_client.client.websocket_connect(f"/ws/workflows/{workflow_id}") as ws:
        # First message(s) should already reflect the completed history --
        # collect messages until we see the COMPLETED state_change that
        # must be part of the snapshot replay itself.
        messages = _drain_until(
            ws, lambda m: m["type"] == "state_change" and m["payload"].get("status") == "COMPLETED", timeout=5
        )

    event_types = [m["payload"]["event_type"] for m in messages if m["type"] == "event"]
    assert "USER_REQUEST_CREATED" in event_types
    assert "WORKFLOW_COMPLETED" in event_types


def test_websocket_message_routed_via_manual_resume_event(api_client):
    """Triggers WORKFLOW_RESUMED via the REST API while connected, and
    confirms it shows up on the socket as both an "event" and
    "agent_activity" message with source_agent="api_user_action"."""
    _configure_single_step_stub(api_client.stub)
    api_client.stub.set_response(  # override: force rejection so we get a BLOCKED workflow to resume
        GoalAnalysis,
        GoalAnalysis(
            goal=GOAL,
            location="Tamil Nadu",
            business_type="food_processing",
            required_workflow=True,
            extracted_entities={"business_name": "Test Co", "scenario": "rejected"},
            missing_info=[],
        ),
    )
    r = api_client.client.post("/api/workflows", json={"user_id": "u1", "goal": GOAL})
    workflow_id = r.json()["workflow_id"]

    deadline = time.time() + 10
    while time.time() < deadline:
        wf = api_client.client.get(f"/api/workflows/{workflow_id}").json()
        if wf.get("status") == "BLOCKED":
            break
        time.sleep(0.05)
    assert wf["status"] == "BLOCKED"

    with api_client.client.websocket_connect(f"/ws/workflows/{workflow_id}") as ws:
        # Drain the snapshot replay first (predicate never true here, so
        # just read a fixed number of messages -- easier: issue the resume
        # call, then look for it specifically).
        resume_resp = api_client.client.post(
            f"/api/workflows/{workflow_id}/events",
            json={"event_type": "WORKFLOW_RESUMED", "payload": {"step_id": "business_registration", "action": "abandon"}},
        )
        assert resume_resp.status_code == 202

        messages = _drain_until(
            ws,
            lambda m: m["type"] == "event" and m["payload"]["event_type"] == "WORKFLOW_RESUMED",
            timeout=10,
        )

    resumed_events = [
        m for m in messages if m["type"] == "event" and m["payload"]["event_type"] == "WORKFLOW_RESUMED"
    ]
    assert len(resumed_events) == 1
    assert resumed_events[0]["payload"]["source_agent"] == "api_user_action"
