"""Common Agent base class.

Every agent: has a name + responsibility, tracks its own status
(idle/running/error) in backend.agents.registry, records every decision it
makes to the audit trail via the append_audit_entry TOOL (never writes to
the audit repo directly -- agents only ever act through registered tools),
and publishes events through the shared event bus (backend.tools.context)
rather than holding its own reference to it.

Subclasses implement ``handle(event)``. ``run(event)`` is what's actually
registered on the event bus -- it wraps ``handle`` with status tracking so
the agent registry reflects real activity.
"""

from __future__ import annotations

import abc
import logging
from typing import Any, Dict, Optional

from backend.agents import registry as agent_registry
from backend.agents.llm_client import LLMClient
from backend.models.enums import EventType, WorkflowStatus
from backend.models.event import Event
from backend.tools.context import get_tool_context
from backend.tools.registry import invoke_tool

logger = logging.getLogger("govflow.agents.base")


class AgentStatus:
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"


class Agent(abc.ABC):
    name: str
    responsibility: str

    def __init__(self, name: str, responsibility: str, llm_client: Optional[LLMClient] = None) -> None:
        self.name = name
        self.responsibility = responsibility
        self.llm_client = llm_client
        agent_registry.update_status(self.name, AgentStatus.IDLE)

    @abc.abstractmethod
    async def handle(self, event: Event) -> None:
        """Subclasses implement their reaction to the event here."""
        raise NotImplementedError

    async def run(self, event: Event) -> None:
        """The actual event-bus handler. Wraps handle() with agent-registry
        status tracking so status/last_action/last_active_at reflect real
        activity, not static placeholder data."""
        agent_registry.update_status(self.name, AgentStatus.RUNNING, last_action=f"handling {event.event_type.value}")
        try:
            await self.handle(event)
            agent_registry.update_status(self.name, AgentStatus.IDLE, last_action=f"handled {event.event_type.value}")
        except Exception as exc:
            agent_registry.update_status(
                self.name, AgentStatus.ERROR, last_action=f"failed handling {event.event_type.value}: {exc}"
            )
            raise

    # ------------------------------------------------------------------
    # Shared helpers available to every subclass
    # ------------------------------------------------------------------

    def audit(
        self,
        workflow_id: str,
        event: str,
        decision: str,
        *,
        source: str = "agent",
        tool: Optional[str] = None,
        api_result: Optional[Dict[str, Any]] = None,
        state_transition: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Records this agent's decision to the audit trail via the
        append_audit_entry tool -- agents never write to the audit repo
        directly."""
        invoke_tool(
            "append_audit_entry",
            {
                "workflow_id": workflow_id,
                "event": event,
                "agent": self.name,
                "decision": decision,
                "source": source,
                "tool": tool,
                "api_result": api_result,
                "state_transition": state_transition,
            },
            workflow_id=workflow_id,
        )

    def is_workflow_gated(self, workflow_id: str) -> bool:
        """True if the workflow is currently WAITING_FOR_USER or BLOCKED --
        agents that act on workflow steps (DocumentAgent,
        DepartmentRouterAgent, ApplicationAgent) must check this before
        proceeding autonomously, since the human-in-the-loop gate can be
        set by a concurrently-running agent (EligibilityAgent) reacting to
        an earlier event in the same chain."""
        ctx = get_tool_context()
        workflow = ctx.workflow_repo.get(workflow_id)
        if workflow is None:
            return False
        return workflow.status in (WorkflowStatus.WAITING_FOR_USER, WorkflowStatus.BLOCKED)

    def get_latest_event_payload(self, workflow_id: str, event_type: EventType) -> Dict[str, Any]:
        """Looks up the most recent event of a given type for this workflow
        from the durable event log. Used when an agent needs data produced
        earlier in the chain (e.g. EligibilityAgent needs GoalInterpreterAgent's
        structured output) but that data isn't in its own triggering event's
        payload -- avoids widening every event's payload just to thread
        state through, at the cost of one repository read."""
        ctx = get_tool_context()
        matches = [e for e in ctx.event_repo.list_for_workflow(workflow_id) if e.event_type == event_type]
        return matches[-1].payload if matches else {}

    async def publish(self, workflow_id: str, event_type: EventType, payload: Dict[str, Any]) -> None:
        """Publishes an event as this agent, via the shared event bus +
        event repository (so it's both dispatched and durably recorded,
        same as WorkflowEngine._record_and_publish)."""
        ctx = get_tool_context()
        evt = Event(workflow_id=workflow_id, event_type=event_type, payload=payload, source_agent=self.name)
        ctx.event_repo.append(evt)
        await ctx.event_bus.publish(evt)
