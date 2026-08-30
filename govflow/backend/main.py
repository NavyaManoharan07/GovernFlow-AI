"""GovFlow AI backend entrypoint.

Part 1 scope: boots FastAPI, wires the event bus + persistence + workflow
engine + mock government API router. No agents, no RAG, no full API
surface yet -- those are Parts 2/3/4.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("govflow.main")

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.agents.llm_client import GeminiClient, StubGeminiClient
from backend.agents.wiring import wire_agents
from backend.api.routes import router as api_router
from backend.api.websocket import ConnectionManager
from backend.api.websocket import router as ws_router
from backend.events.bus import get_event_bus
from backend.events.registry import wire_registry_to_bus
from backend.services.factory import get_repositories
from backend.tools.context import ToolContext, set_tool_context
from backend.workflows.engine import WorkflowEngine
from mock_services.router import router as mock_router


def _build_llm_client():
    """Real GeminiClient if GEMINI_API_KEY is configured, otherwise a
    StubGeminiClient with no canned responses -- the backend still boots
    and every non-agent route works, but any event that reaches an
    LLM-backed agent will raise LLMClientError until a key is set. This
    keeps local boot reliable (Part 1's "server boots" guarantee) even
    with no Gemini key configured, per "reliability > complexity"."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
        logger.info("Gemini configured: model=%s", model)
        return GeminiClient(api_key=api_key, model=model)
    logger.warning(
        "GEMINI_API_KEY not set -- using StubGeminiClient with no canned responses. "
        "LLM-backed agents (GoalInterpreter/WorkflowPlanner/Eligibility) will raise "
        "LLMClientError if triggered. Set GEMINI_API_KEY in .env for real runs."
    )
    return StubGeminiClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    event_bus_mode = os.environ.get("EVENT_BUS_MODE", "local")
    persistence_mode = os.environ.get("PERSISTENCE_MODE", "local")
    logger.info(
        "starting GovFlow AI backend | event_bus_mode=%s persistence_mode=%s",
        event_bus_mode,
        persistence_mode,
    )

    event_bus = get_event_bus()
    workflow_repo, event_repo, audit_repo, notification_repo = get_repositories()

    engine = WorkflowEngine(event_bus, workflow_repo, event_repo, audit_repo)
    engine.register_core_handlers()

    set_tool_context(
        ToolContext(
            workflow_repo=workflow_repo,
            event_repo=event_repo,
            audit_repo=audit_repo,
            notification_repo=notification_repo,
            event_bus=event_bus,
            engine=engine,
        )
    )

    llm_client = _build_llm_client()
    agents = wire_agents(llm_client)

    wire_registry_to_bus(event_bus, event_repo=event_repo)

    # WebSocket broadcaster: registered directly on the bus (subscribe_all),
    # deliberately NOT through the declarative registry / with_retry --  see
    # backend/api/websocket.py's module docstring for why.
    connection_manager = ConnectionManager(workflow_repo, event_repo, audit_repo)
    event_bus.subscribe_all(connection_manager.on_event)

    app.state.event_bus = event_bus
    app.state.workflow_repo = workflow_repo
    app.state.event_repo = event_repo
    app.state.audit_repo = audit_repo
    app.state.notification_repo = notification_repo
    app.state.workflow_engine = engine
    app.state.agents = agents
    app.state.connection_manager = connection_manager

    logger.info("GovFlow AI backend ready (agents wired, RAG loaded, WS broadcaster attached)")
    yield
    logger.info("shutting down GovFlow AI backend")


def create_app() -> FastAPI:
    app = FastAPI(
        title="GovFlow AI",
        description="Autonomous Government Service Orchestration Agent -- REST API + WebSocket (Part 3)",
        version="0.3.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Never leak a stack trace to the client -- log it server-side with
        # full detail, return a safe, generic body.
        logger.exception("unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_server_error", "detail": "An unexpected error occurred."},
        )

    app.include_router(api_router)
    app.include_router(ws_router)
    app.include_router(mock_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
