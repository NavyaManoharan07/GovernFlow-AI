"""Wires the 10 agents onto the event bus via the declarative handler
registry -- no hardcoded sequential orchestration function. Each agent
subscribes only to the event type(s) that trigger it; the event bus fans
events out, agents react, and the chain cascades autonomously.

Event flow (see individual agent docstrings for why each edge was chosen):

    USER_REQUEST_CREATED   -> GoalInterpreterAgent      -> GOAL_ANALYZED
    GOAL_ANALYZED           -> RegulationAgent            -> REQUIREMENTS_IDENTIFIED
    REQUIREMENTS_IDENTIFIED -> WorkflowPlannerAgent        -> WORKFLOW_CREATED (+ NEXT_ACTION_TRIGGERED, via engine)
    WORKFLOW_CREATED        -> EligibilityAgent             -> ELIGIBILITY_CHECKED | (gate: BLOCKED/WAITING_FOR_USER)
    NEXT_ACTION_TRIGGERED   -> DocumentAgent                -> DOCUMENTS_VALIDATED | DOCUMENT_MISSING
    DOCUMENTS_VALIDATED     -> DepartmentRouterAgent          -> APPLICATION_READY
    APPLICATION_READY       -> ApplicationAgent                -> APPLICATION_SUBMITTED
    APPLICATION_SUBMITTED   -> StatusMonitorAgent (background poll) -> APPLICATION_STATUS_CHANGED, then
                                                                        APPLICATION_APPROVED | APPLICATION_REJECTED | DOCUMENT_MISSING
    APPLICATION_APPROVED    -> WorkflowEngine (core handler)  -> complete_step -> WORKFLOW_COMPLETED | NEXT_ACTION_TRIGGERED (loop)
    APPLICATION_REJECTED    -> WorkflowEngine (core handler)  -> block_step (BLOCKED) + USER_ACTION_REQUIRED
    DOCUMENT_MISSING        -> WorkflowEngine (core handler)  -> block_step (WAITING_FOR_USER) + USER_ACTION_REQUIRED
    WORKFLOW_RESUMED        -> WorkflowEngine (core handler)  -> resume_step / resume workflow -> NEXT_ACTION_TRIGGERED

    NotificationAgent subscribes broadly (see NOTIFIED_EVENT_TYPES below).
    AuditAgent subscribes to every event via a wildcard handler.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.agents.application import ApplicationAgent
from backend.agents.audit import AuditAgent
from backend.agents.department_router import DepartmentRouterAgent
from backend.agents.document import DocumentAgent
from backend.agents.eligibility import EligibilityAgent
from backend.agents.goal_interpreter import GoalInterpreterAgent
from backend.agents.llm_client import LLMClient
from backend.agents.notification import NotificationAgent
from backend.agents.regulation import RegulationAgent
from backend.agents.status_monitor import StatusMonitorAgent
from backend.agents.workflow_planner import WorkflowPlannerAgent
from backend.events.registry import register_handler, register_wildcard_handler
from backend.models.enums import EventType

NOTIFIED_EVENT_TYPES = [
    EventType.GOAL_ANALYZED,
    EventType.WORKFLOW_CREATED,
    EventType.ELIGIBILITY_CHECKED,
    EventType.DOCUMENTS_VALIDATED,
    EventType.DOCUMENT_MISSING,
    EventType.APPLICATION_SUBMITTED,
    EventType.APPLICATION_STATUS_CHANGED,
    EventType.APPLICATION_APPROVED,
    EventType.APPLICATION_REJECTED,
    EventType.USER_ACTION_REQUIRED,
    EventType.WORKFLOW_COMPLETED,
    EventType.WORKFLOW_FAILED,
    EventType.WORKFLOW_RESUMED,
]


@dataclass
class WiredAgents:
    goal_interpreter: GoalInterpreterAgent
    regulation: RegulationAgent
    workflow_planner: WorkflowPlannerAgent
    eligibility: EligibilityAgent
    document: DocumentAgent
    department_router: DepartmentRouterAgent
    application: ApplicationAgent
    status_monitor: StatusMonitorAgent
    notification: NotificationAgent
    audit: AuditAgent


def wire_agents(llm_client: LLMClient) -> WiredAgents:
    """Instantiates every agent and registers its handler(s) on the
    declarative event registry. Call once at startup, after
    backend.tools.context.set_tool_context(...) and before
    backend.events.registry.wire_registry_to_bus(...)."""
    agents = WiredAgents(
        goal_interpreter=GoalInterpreterAgent(llm_client),
        regulation=RegulationAgent(),
        workflow_planner=WorkflowPlannerAgent(llm_client),
        eligibility=EligibilityAgent(llm_client),
        document=DocumentAgent(),
        department_router=DepartmentRouterAgent(),
        application=ApplicationAgent(),
        status_monitor=StatusMonitorAgent(),
        notification=NotificationAgent(),
        audit=AuditAgent(),
    )

    register_handler(EventType.USER_REQUEST_CREATED, agents.goal_interpreter.run)
    register_handler(EventType.GOAL_ANALYZED, agents.regulation.run)
    register_handler(EventType.REQUIREMENTS_IDENTIFIED, agents.workflow_planner.run)
    register_handler(EventType.WORKFLOW_CREATED, agents.eligibility.run)
    register_handler(EventType.NEXT_ACTION_TRIGGERED, agents.document.run)
    register_handler(EventType.DOCUMENTS_VALIDATED, agents.department_router.run)
    register_handler(EventType.APPLICATION_READY, agents.application.run)
    register_handler(EventType.APPLICATION_SUBMITTED, agents.status_monitor.run)

    for event_type in NOTIFIED_EVENT_TYPES:
        register_handler(event_type, agents.notification.run)

    register_wildcard_handler(agents.audit.run)

    return agents
