"""AuditAgent: bus-wide safety net.

Every other agent logs its own decisions via Agent.audit() (which calls
the append_audit_entry tool). This agent is registered as a WILDCARD
handler (backend.events.registry.register_wildcard_handler) so it sees
literally every event published on the bus and records a second,
independent audit row for it -- guaranteeing the audit trail is complete
even if a future agent (or a Part 3/4 addition) forgets to call
self.audit(). Its row is clearly distinguished (source="bus_wide_audit_listener")
from the originating agent's own decision row.
"""

from __future__ import annotations

from backend.agents.base import Agent
from backend.models.event import Event
from backend.tools.registry import invoke_tool


class AuditAgent(Agent):
    def __init__(self) -> None:
        super().__init__("AuditAgent", "Guarantees every event on the bus is recorded in the audit trail")

    async def handle(self, event: Event) -> None:
        invoke_tool(
            "append_audit_entry",
            {
                "workflow_id": event.workflow_id,
                "event": event.event_type.value,
                "agent": event.source_agent,
                "decision": f"event {event.event_type.value} observed on bus (correlation_id={event.correlation_id})",
                "source": "bus_wide_audit_listener",
                "tool": None,
                "api_result": None,
                "state_transition": {"payload_keys": sorted(event.payload.keys())},
            },
            workflow_id=event.workflow_id,
        )
