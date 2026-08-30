"""ApplicationAgent: prepares and submits the application to the routed
mock service. No LLM call -- payload preparation and field presence are
validated deterministically via the tool's own Pydantic input schema."""

from __future__ import annotations

from backend.agents.base import Agent
from backend.models.enums import EventType
from backend.models.event import Event
from backend.tools.context import get_tool_context
from backend.tools.registry import invoke_tool


class ApplicationAgent(Agent):
    def __init__(self) -> None:
        super().__init__("ApplicationAgent", "Prepares and submits applications to the routed mock service")

    async def handle(self, event: Event) -> None:
        if event.event_type != EventType.APPLICATION_READY:
            return

        workflow_id = event.workflow_id
        if self.is_workflow_gated(workflow_id):
            return

        step_id = event.payload["step_id"]
        service = event.payload["service"]
        tool_name = event.payload["tool_name"]

        ctx = get_tool_context()
        workflow = ctx.workflow_repo.get(workflow_id)
        if workflow is None:
            return

        goal_analysis = self.get_latest_event_payload(workflow_id, EventType.GOAL_ANALYZED)
        extracted = goal_analysis.get("extracted_entities") or {}
        business_name = extracted.get("business_name") or f"{workflow.goal[:60].strip()} Business"
        # An explicit workflow.metadata["scenario"] (set by the Part 3 demo
        # orchestrator) always wins over whatever Gemini's free-form
        # extraction happened to produce -- this is what makes the demo's
        # mock-API path deterministic regardless of LLM variability, while
        # leaving real user-submitted goals (no metadata set) fully organic.
        scenario = (workflow.metadata or {}).get("scenario") or extracted.get("scenario")

        submit_payload = {"business_name": business_name}
        if scenario:
            submit_payload["scenario"] = scenario

        # Tool schema validation (ApplicationSubmitInput) happens inside
        # invoke_tool -- a malformed payload never reaches the mock API.
        result = invoke_tool(tool_name, submit_payload, workflow_id=workflow_id)

        application_record = result.model_dump()
        application_record["step_id"] = step_id
        updated_applications = list(workflow.applications) + [application_record]
        invoke_tool(
            "update_workflow_state",
            {"workflow_id": workflow_id, "patch": {"applications": updated_applications}},
            workflow_id=workflow_id,
        )

        self.audit(
            workflow_id,
            event=EventType.APPLICATION_SUBMITTED.value,
            decision=f"submitted step={step_id} service={service} application_id={result.application_id}",
            tool=tool_name,
            api_result=result.model_dump(),
        )
        await self.publish(
            workflow_id,
            EventType.APPLICATION_SUBMITTED,
            {"step_id": step_id, "service": service, "application_id": result.application_id},
        )
