"""DepartmentRouterAgent: deterministically maps a validated step to the
correct mock-service tool. Pure routing logic -- no LLM call, per the task
brief ("this is routing logic, not something that needs an LLM call")."""

from __future__ import annotations

from backend.agents.base import Agent
from backend.models.enums import EventType
from backend.models.event import Event

SERVICE_TOOL_MAP = {
    "business_registration": "call_business_registration_api",
    "tax_registration": "call_tax_registration_api",
    "food_license": "call_food_license_api",
    "local_approval": "call_local_approval_api",
}


class DepartmentRouterAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            "DepartmentRouterAgent",
            "Deterministically routes each ready step to the correct mock government service",
        )

    async def handle(self, event: Event) -> None:
        if event.event_type != EventType.DOCUMENTS_VALIDATED:
            return

        workflow_id = event.workflow_id
        if self.is_workflow_gated(workflow_id):
            return

        step_id = event.payload.get("step_id")
        service = event.payload.get("service")
        tool_name = SERVICE_TOOL_MAP.get(service)

        if tool_name is None:
            self.audit(
                workflow_id,
                event="ROUTING_FAILED",
                decision=f"no route registered for service={service!r} (step={step_id})",
                source="error",
            )
            return

        self.audit(
            workflow_id,
            event=EventType.APPLICATION_READY.value,
            decision=f"routed step={step_id} service={service} -> tool={tool_name}",
            tool=tool_name,
        )
        await self.publish(
            workflow_id,
            EventType.APPLICATION_READY,
            {"step_id": step_id, "service": service, "tool_name": tool_name},
        )
