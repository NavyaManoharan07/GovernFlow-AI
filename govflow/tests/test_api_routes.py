import time

from backend.agents.schemas import EligibilityResult, GoalAnalysis, ServicePlan

GOAL = "I want to start a small food-processing business in Tamil Nadu"


def _configure_happy_path(stub, extracted_entities=None):
    stub.set_response(
        GoalAnalysis,
        GoalAnalysis(
            goal=GOAL,
            location="Tamil Nadu",
            business_type="food_processing",
            required_workflow=True,
            extracted_entities=extracted_entities or {"business_name": "TN Snacks Co"},
            missing_info=[],
        ),
    )
    stub.set_response(
        ServicePlan,
        ServicePlan(
            services=["business_registration"],
            dependencies={"business_registration": []},
            reasoning="Only business registration needed for this simplified test.",
        ),
    )
    stub.set_response(
        EligibilityResult, EligibilityResult(status="eligible", missing_fields=[], reasoning="ok")
    )


def _wait_for_workflow(client, workflow_id, timeout=10):
    deadline = time.time() + timeout
    terminal = {"COMPLETED", "FAILED", "BLOCKED", "WAITING_FOR_USER"}
    while time.time() < deadline:
        r = client.get(f"/api/workflows/{workflow_id}")
        if r.status_code == 200 and r.json()["status"] in terminal:
            return r.json()
        time.sleep(0.05)
    raise TimeoutError(f"workflow {workflow_id} did not reach a terminal state in {timeout}s")


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


def test_health(api_client):
    r = api_client.client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# POST /api/workflows, GET /api/workflows/{id}
# ---------------------------------------------------------------------------


def test_create_workflow_returns_202_immediately(api_client):
    _configure_happy_path(api_client.stub)
    r = api_client.client.post("/api/workflows", json={"user_id": "u1", "goal": GOAL})
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "ACCEPTED"
    assert body["workflow_id"]
    assert body["goal"] == GOAL


def test_create_workflow_validation_error_returns_422(api_client):
    r = api_client.client.post("/api/workflows", json={"user_id": "u1"})  # missing goal
    assert r.status_code == 422


def test_create_workflow_then_get_reaches_completed(api_client):
    _configure_happy_path(api_client.stub)
    r = api_client.client.post("/api/workflows", json={"user_id": "u1", "goal": GOAL})
    workflow_id = r.json()["workflow_id"]

    workflow = _wait_for_workflow(api_client.client, workflow_id)
    assert workflow["status"] == "COMPLETED"
    assert workflow["completed_steps"] == ["business_registration"]


def test_get_unknown_workflow_returns_404(api_client):
    r = api_client.client.get("/api/workflows/does-not-exist")
    assert r.status_code == 404


def test_get_workflow_graph_unavailable_for_unknown_workflow(api_client):
    r = api_client.client.get("/api/workflows/does-not-exist/graph")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert body["steps"] == []


def test_get_workflow_graph_returns_real_dag_with_dependencies(api_client):
    _configure_happy_path(api_client.stub)
    r = api_client.client.post("/api/workflows", json={"user_id": "u1", "goal": GOAL})
    workflow_id = r.json()["workflow_id"]
    _wait_for_workflow(api_client.client, workflow_id)

    r = api_client.client.get(f"/api/workflows/{workflow_id}/graph")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert len(body["steps"]) == 1
    step = body["steps"][0]
    assert step["id"] == "business_registration"
    assert step["depends_on"] == []
    assert step["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# GET .../events, GET .../audit
# ---------------------------------------------------------------------------


def test_events_and_audit_for_unknown_workflow_return_empty_list_not_404(api_client):
    r = api_client.client.get("/api/workflows/does-not-exist/events")
    assert r.status_code == 200
    assert r.json() == []

    r = api_client.client.get("/api/workflows/does-not-exist/audit")
    assert r.status_code == 200
    assert r.json() == []


def test_events_and_audit_populated_after_workflow_completes(api_client):
    _configure_happy_path(api_client.stub)
    r = api_client.client.post("/api/workflows", json={"user_id": "u1", "goal": GOAL})
    workflow_id = r.json()["workflow_id"]
    _wait_for_workflow(api_client.client, workflow_id)

    r = api_client.client.get(f"/api/workflows/{workflow_id}/events")
    assert r.status_code == 200
    event_types = [e["event_type"] for e in r.json()]
    assert "USER_REQUEST_CREATED" in event_types
    assert "WORKFLOW_COMPLETED" in event_types

    r = api_client.client.get(f"/api/workflows/{workflow_id}/audit")
    assert r.status_code == 200
    audit = r.json()
    assert len(audit) > 0
    assert all({"timestamp", "event", "agent", "decision", "tool"} <= set(entry.keys()) for entry in audit)


# ---------------------------------------------------------------------------
# POST /api/workflows/{id}/events
# ---------------------------------------------------------------------------


def test_manual_event_disallowed_type_returns_422(api_client):
    _configure_happy_path(api_client.stub)
    r = api_client.client.post("/api/workflows", json={"user_id": "u1", "goal": GOAL})
    workflow_id = r.json()["workflow_id"]
    _wait_for_workflow(api_client.client, workflow_id)

    r = api_client.client.post(
        f"/api/workflows/{workflow_id}/events", json={"event_type": "WORKFLOW_COMPLETED", "payload": {}}
    )
    assert r.status_code == 422


def test_manual_event_malformed_payload_returns_422(api_client):
    _configure_happy_path(api_client.stub)
    r = api_client.client.post("/api/workflows", json={"user_id": "u1", "goal": GOAL})
    workflow_id = r.json()["workflow_id"]
    _wait_for_workflow(api_client.client, workflow_id)

    r = api_client.client.post(
        f"/api/workflows/{workflow_id}/events",
        json={"event_type": "WORKFLOW_RESUMED", "payload": {"action": "not_valid"}},
    )
    assert r.status_code == 422


def test_manual_event_unknown_workflow_returns_404(api_client):
    r = api_client.client.post(
        "/api/workflows/does-not-exist/events", json={"event_type": "WORKFLOW_RESUMED", "payload": {}}
    )
    assert r.status_code == 404


def test_manual_event_resumes_blocked_workflow(api_client):
    _configure_happy_path(api_client.stub, extracted_entities={"business_name": "Test Co", "scenario": "rejected"})
    r = api_client.client.post("/api/workflows", json={"user_id": "u1", "goal": GOAL})
    workflow_id = r.json()["workflow_id"]
    workflow = _wait_for_workflow(api_client.client, workflow_id)
    assert workflow["status"] == "BLOCKED"

    r = api_client.client.post(
        f"/api/workflows/{workflow_id}/events",
        json={"event_type": "WORKFLOW_RESUMED", "payload": {"step_id": "business_registration", "action": "abandon"}},
    )
    assert r.status_code == 202

    r = api_client.client.get(f"/api/workflows/{workflow_id}")
    assert r.json()["status"] == "FAILED"
    assert "business_registration" in r.json()["failed_steps"]


# ---------------------------------------------------------------------------
# GET /api/agents, GET /api/services
# ---------------------------------------------------------------------------


def test_list_agents_returns_all_ten_with_real_shape(api_client):
    r = api_client.client.get("/api/agents")
    assert r.status_code == 200
    agents = r.json()
    assert len(agents) == 10
    names = {a["name"] for a in agents}
    assert "GoalInterpreterAgent" in names
    assert "AuditAgent" in names
    for a in agents:
        assert a["status"] in ("idle", "running", "error")


def test_list_services_returns_four_catalog_services(api_client):
    r = api_client.client.get("/api/services")
    assert r.status_code == 200
    services = r.json()
    assert {s["service"] for s in services} == {
        "business_registration",
        "tax_registration",
        "food_license",
        "local_approval",
    }
    for s in services:
        assert s["department"]
        assert s["tool_name"].startswith("call_")
        assert s["mock_data"] is True


# ---------------------------------------------------------------------------
# POST /api/demo/run
# ---------------------------------------------------------------------------


def test_demo_run_clean_scenario_completes(api_client):
    api_client.stub.set_response(
        GoalAnalysis,
        GoalAnalysis(
            goal="I want to start a small food-processing business in Tamil Nadu",
            location="Tamil Nadu",
            business_type="food_processing",
            required_workflow=True,
            extracted_entities={"business_name": "TN Snacks Co"},
            missing_info=[],
        ),
    )
    api_client.stub.set_response(
        ServicePlan,
        ServicePlan(
            services=["business_registration", "tax_registration", "food_license", "local_approval"],
            dependencies={
                "business_registration": [],
                "tax_registration": ["business_registration"],
                "food_license": ["business_registration"],
                "local_approval": ["tax_registration", "food_license"],
            },
            reasoning="all four",
        ),
    )
    api_client.stub.set_response(EligibilityResult, EligibilityResult(status="eligible", missing_fields=[], reasoning="ok"))

    r = api_client.client.post("/api/demo/run", params={"scenario": "clean"})
    assert r.status_code == 202
    workflow_id = r.json()["workflow_id"]

    workflow = _wait_for_workflow(api_client.client, workflow_id, timeout=15)
    assert workflow["status"] == "COMPLETED"
    assert len(workflow["applications"]) == 4


def test_demo_run_invalid_scenario_returns_422(api_client):
    r = api_client.client.post("/api/demo/run", params={"scenario": "not_a_real_scenario"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


def test_rate_limit_kicks_in_on_create_workflow(api_client, monkeypatch):
    monkeypatch.setenv("API_RATE_LIMIT_PER_MINUTE", "2")
    from backend.api.rate_limit import reset_api_rate_limiter

    reset_api_rate_limiter()

    _configure_happy_path(api_client.stub)
    for _ in range(2):
        r = api_client.client.post("/api/workflows", json={"user_id": "u1", "goal": GOAL})
        assert r.status_code == 202

    r = api_client.client.post("/api/workflows", json={"user_id": "u1", "goal": GOAL})
    assert r.status_code == 429


# ---------------------------------------------------------------------------
# API key auth placeholder
# ---------------------------------------------------------------------------


def test_auth_disabled_by_default(api_client):
    _configure_happy_path(api_client.stub)
    r = api_client.client.post("/api/workflows", json={"user_id": "u1", "goal": GOAL})
    assert r.status_code == 202  # no X-API-Key header needed


def test_auth_enforced_when_enabled(api_client, monkeypatch):
    monkeypatch.setenv("API_KEY_REQUIRED", "true")
    monkeypatch.setenv("API_KEY", "secret-123")

    r = api_client.client.post("/api/workflows", json={"user_id": "u1", "goal": GOAL})
    assert r.status_code == 401

    _configure_happy_path(api_client.stub)
    r = api_client.client.post(
        "/api/workflows", json={"user_id": "u1", "goal": GOAL}, headers={"X-API-Key": "secret-123"}
    )
    assert r.status_code == 202


# ---------------------------------------------------------------------------
# Retry-with-backoff, exercised through the real API path (not just the
# isolated with_retry unit test from Part 2) -- confirms
# wire_registry_to_bus's retry wrapping is actually active on the handlers
# main.py wires up, and that exhausted retries fail gracefully (a clear
# WORKFLOW_FAILED event + a surfaced notification) instead of leaving the
# workflow silently stuck.
# ---------------------------------------------------------------------------


def test_exhausted_retries_on_llm_failure_produce_workflow_failed_via_api(api_client):
    # Deliberately leave the stub with NO canned GoalAnalysis response --
    # every call to generate_structured() raises LLMClientError, so
    # GoalInterpreterAgent.run() fails on every one of with_retry's 3
    # attempts (registered via wire_registry_to_bus in the real app
    # lifespan, exactly as in production).
    r = api_client.client.post("/api/workflows", json={"user_id": "u1", "goal": GOAL})
    assert r.status_code == 202  # never blocks on the agent chain, even on failure
    workflow_id = r.json()["workflow_id"]

    deadline = time.time() + 10
    event_types = []
    while time.time() < deadline:
        events = api_client.client.get(f"/api/workflows/{workflow_id}/events").json()
        event_types = [e["event_type"] for e in events]
        if "WORKFLOW_FAILED" in event_types:
            break
        time.sleep(0.05)

    assert "USER_REQUEST_CREATED" in event_types
    assert "WORKFLOW_FAILED" in event_types, f"retries never exhausted gracefully; saw {event_types}"

    # NotificationAgent must have surfaced it too (it's subscribed to
    # WORKFLOW_FAILED -- see NOTIFIED_EVENT_TYPES in backend/agents/wiring.py).
    audit = api_client.client.get(f"/api/workflows/{workflow_id}/audit").json()
    notification_entries = [a for a in audit if a["agent"] == "NotificationAgent"]
    assert any("failed" in a["decision"].lower() for a in notification_entries)
