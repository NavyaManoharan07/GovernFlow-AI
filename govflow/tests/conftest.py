import dataclasses
from unittest.mock import patch

import pytest

from backend.agents import registry as agent_registry
from backend.agents.llm_client import StubGeminiClient
from backend.agents.wiring import wire_agents
from backend.api.rate_limit import reset_api_rate_limiter
from backend.events.bus import InProcessEventBus, reset_event_bus
from backend.events.registry import clear_registry, wire_registry_to_bus
from backend.rag.retriever import reset_retriever
from backend.services.db import reset_connection_cache
from backend.services.sqlite_repo import (
    SQLiteAuditRepository,
    SQLiteEventRepository,
    SQLiteNotificationRepository,
    SQLiteWorkflowRepository,
)
from backend.tools.context import ToolContext, reset_tool_context, set_tool_context
from backend.tools.rate_limiter import reset_rate_limiter
from backend.workflows.engine import WorkflowEngine
from mock_services.client import reset_mock_client


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Ensures each test starts with a clean event bus, handler registry,
    tool context, rate limiters, mock government API client, and agent
    registry -- these are all process-wide singletons."""
    reset_event_bus()
    clear_registry()
    reset_mock_client()
    reset_tool_context()
    reset_rate_limiter()
    reset_api_rate_limiter()
    agent_registry.reset()
    yield
    reset_event_bus()
    clear_registry()
    reset_mock_client()
    reset_tool_context()
    reset_rate_limiter()
    reset_api_rate_limiter()
    agent_registry.reset()


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Points the SQLite layer at a throwaway file for the duration of the test."""
    db_path = tmp_path / "test_govflow.db"
    monkeypatch.setenv("GOVFLOW_DB_PATH", str(db_path))
    reset_connection_cache()
    yield db_path
    reset_connection_cache()


@dataclasses.dataclass
class WiredSystem:
    bus: InProcessEventBus
    workflow_repo: SQLiteWorkflowRepository
    event_repo: SQLiteEventRepository
    audit_repo: SQLiteAuditRepository
    notification_repo: SQLiteNotificationRepository
    engine: WorkflowEngine
    agents: object  # backend.agents.wiring.WiredAgents
    stub: StubGeminiClient


@dataclasses.dataclass
class BareContext:
    bus: InProcessEventBus
    workflow_repo: SQLiteWorkflowRepository
    event_repo: SQLiteEventRepository
    audit_repo: SQLiteAuditRepository
    notification_repo: SQLiteNotificationRepository
    engine: WorkflowEngine
    stub: StubGeminiClient


@pytest.fixture
def bare_context(temp_db, monkeypatch):
    """Same repos/engine/tool-context setup as wired_system, but with NO
    agents registered on the bus -- for isolated per-agent unit tests that
    construct one agent directly and call agent.handle(event) / agent.run(event)
    themselves, so a downstream agent cascading (or failing without a
    canned stub response) can never interfere with the assertions."""
    monkeypatch.setenv("STATUS_POLL_INTERVAL_SECONDS", "0.02")
    monkeypatch.setenv("STATUS_MAX_POLLS", "8")
    reset_retriever()

    bus = InProcessEventBus()
    workflow_repo = SQLiteWorkflowRepository()
    event_repo = SQLiteEventRepository()
    audit_repo = SQLiteAuditRepository()
    notification_repo = SQLiteNotificationRepository()

    engine = WorkflowEngine(bus, workflow_repo, event_repo, audit_repo)
    engine.register_core_handlers()
    wire_registry_to_bus(bus, event_repo=event_repo)  # only the engine's own core handlers are registered at this point

    set_tool_context(
        ToolContext(
            workflow_repo=workflow_repo,
            event_repo=event_repo,
            audit_repo=audit_repo,
            notification_repo=notification_repo,
            event_bus=bus,
            engine=engine,
        )
    )

    return BareContext(
        bus=bus,
        workflow_repo=workflow_repo,
        event_repo=event_repo,
        audit_repo=audit_repo,
        notification_repo=notification_repo,
        engine=engine,
        stub=StubGeminiClient(),
    )


@pytest.fixture
def wired_system(temp_db, monkeypatch):
    """Full stack wired together exactly like backend/main.py's lifespan,
    but with SQLite pointed at a throwaway file, an isolated InProcessEventBus,
    and a StubGeminiClient (no canned responses registered yet -- tests call
    wired.stub.set_response(...) before publishing the event that needs it).

    Also speeds up StatusMonitorAgent's polling so tests don't take real
    seconds per application.
    """
    monkeypatch.setenv("STATUS_POLL_INTERVAL_SECONDS", "0.02")
    monkeypatch.setenv("STATUS_MAX_POLLS", "8")
    reset_retriever()

    bus = InProcessEventBus()
    workflow_repo = SQLiteWorkflowRepository()
    event_repo = SQLiteEventRepository()
    audit_repo = SQLiteAuditRepository()
    notification_repo = SQLiteNotificationRepository()

    engine = WorkflowEngine(bus, workflow_repo, event_repo, audit_repo)
    engine.register_core_handlers()

    set_tool_context(
        ToolContext(
            workflow_repo=workflow_repo,
            event_repo=event_repo,
            audit_repo=audit_repo,
            notification_repo=notification_repo,
            event_bus=bus,
            engine=engine,
        )
    )

    stub = StubGeminiClient()
    agents = wire_agents(stub)
    wire_registry_to_bus(bus, event_repo=event_repo)

    return WiredSystem(
        bus=bus,
        workflow_repo=workflow_repo,
        event_repo=event_repo,
        audit_repo=audit_repo,
        notification_repo=notification_repo,
        engine=engine,
        agents=agents,
        stub=stub,
    )


@dataclasses.dataclass
class ApiTestContext:
    client: object  # fastapi.testclient.TestClient
    stub: StubGeminiClient


@pytest.fixture
def api_client(temp_db, monkeypatch):
    """Boots the REAL backend.main.app (Part 3's actual FastAPI app,
    lifespan and all) with SQLite pointed at a throwaway file and a fast
    polling interval, with backend.main._build_llm_client patched to
    return a StubGeminiClient instead of requiring GEMINI_API_KEY. Tests
    call `ctx.stub.set_response(...)` (before or after entering the
    fixture -- StubGeminiClient reads its canned-response dict at call
    time) and drive everything through `ctx.client` (a real TestClient),
    exactly as a browser/curl would.
    """
    monkeypatch.setenv("STATUS_POLL_INTERVAL_SECONDS", "0.05")
    monkeypatch.setenv("STATUS_MAX_POLLS", "6")

    import backend.main as main_module
    from fastapi.testclient import TestClient

    stub = StubGeminiClient()
    with patch.object(main_module, "_build_llm_client", return_value=stub):
        with TestClient(main_module.app) as client:
            yield ApiTestContext(client=client, stub=stub)
