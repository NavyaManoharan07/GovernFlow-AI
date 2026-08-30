"""RegulationAgent: retrieves applicable rules from the RAG knowledge base.

No Gemini call -- purely deterministic tool orchestration (retrieve_rules
per catalog service) and forwards exactly what retrieval returned. Never
invents a rule: if retrieval comes back empty for a service, that service's
entry in rules_by_service is an empty list, not a fabricated requirement.
"""

from __future__ import annotations

from backend.agents.base import Agent
from backend.models.enums import EventType
from backend.models.event import Event
from backend.tools.registry import invoke_tool

CATALOG_SERVICES = ["business_registration", "tax_registration", "food_license", "local_approval"]


class RegulationAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            "RegulationAgent",
            "Retrieves applicable rules from the RAG knowledge base, with citations",
        )

    async def handle(self, event: Event) -> None:
        if event.event_type != EventType.GOAL_ANALYZED:
            return

        workflow_id = event.workflow_id
        goal = event.payload.get("goal", "")
        business_type = event.payload.get("business_type") or ""

        rules_by_service: dict[str, list[dict]] = {}
        for service in CATALOG_SERVICES:
            query = f"{goal} {business_type} requirements dependencies eligibility for {service}".strip()
            result = invoke_tool("retrieve_rules", {"query": query, "service": service, "top_k": 5}, workflow_id=workflow_id)
            rules_by_service[service] = [r.model_dump() for r in result.rules]

        total_rules = sum(len(v) for v in rules_by_service.values())
        self.audit(
            workflow_id,
            event=EventType.REQUIREMENTS_IDENTIFIED.value,
            decision=f"retrieved {total_rules} rule chunks across {len(CATALOG_SERVICES)} catalog services",
            tool="retrieve_rules",
        )

        payload = {"rules_by_service": rules_by_service, "goal_analysis": event.payload}
        await self.publish(workflow_id, EventType.REQUIREMENTS_IDENTIFIED, payload)
