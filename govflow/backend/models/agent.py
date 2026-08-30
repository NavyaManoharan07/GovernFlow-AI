from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentInfo(BaseModel):
    name: str
    responsibility: str
    status: str = "idle"
    last_action: Optional[str] = None
    last_active_at: Optional[datetime] = None


# Static fallback list of the 10 agents, matching the classes actually
# implemented in backend/agents/ (Part 2). backend.agents.registry.AgentRegistry
# seeds itself from this list at startup, then updates entries in place as
# agents actually run -- this is no longer static placeholder data once the
# registry is wired up.
PLANNED_AGENTS = [
    AgentInfo(name="GoalInterpreterAgent", responsibility="Parses the user's high-level goal into structured intent via Gemini"),
    AgentInfo(name="RegulationAgent", responsibility="Retrieves applicable rules from the RAG knowledge base, with citations"),
    AgentInfo(name="WorkflowPlannerAgent", responsibility="Derives the required services + dependency graph via Gemini and builds the WorkflowGraph"),
    AgentInfo(name="EligibilityAgent", responsibility="Checks eligibility against retrieved rules via Gemini"),
    AgentInfo(name="DocumentAgent", responsibility="Builds the document checklist and validates provided documents"),
    AgentInfo(name="DepartmentRouterAgent", responsibility="Deterministically routes each ready step to the correct mock government service"),
    AgentInfo(name="ApplicationAgent", responsibility="Prepares and submits applications to the routed mock service"),
    AgentInfo(name="StatusMonitorAgent", responsibility="Polls application status and reacts to approval/rejection/missing documents"),
    AgentInfo(name="NotificationAgent", responsibility="Produces human-readable notifications for workflow events"),
    AgentInfo(name="AuditAgent", responsibility="Guarantees every event on the bus is recorded in the audit trail"),
]
