"""DocumentAgent: builds the document checklist per service via RAG and
validates provided documents via the mock validate_document tool.

No Gemini call -- checklist derivation is a RAG lookup (deterministic
given the same knowledge base) and validation is a tool call; there's no
open-ended reasoning step here, matching "deterministic code decides
control flow" wherever an LLM call wouldn't add anything.

Part 2 has no document-upload UI yet (that's Part 3/4), so "documents the
applicant provided" is approximated: the checklist itself, UNLESS the
goal analysis carries an explicit scenario hint of "document_missing" (via
GoalInterpreterAgent's extracted_entities), in which case an empty
document list is sent instead -- so the DOCUMENT_MISSING path is still
genuinely exercised end-to-end through the real mock API, not faked.
"""

from __future__ import annotations

from backend.agents.base import Agent
from backend.models.enums import EventType
from backend.models.event import Event
from backend.tools.context import get_tool_context
from backend.tools.registry import invoke_tool


class DocumentAgent(Agent):
    def __init__(self) -> None:
        super().__init__("DocumentAgent", "Builds the document checklist and validates provided documents")

    async def handle(self, event: Event) -> None:
        if event.event_type != EventType.NEXT_ACTION_TRIGGERED:
            return

        workflow_id = event.workflow_id
        if self.is_workflow_gated(workflow_id):
            return

        ctx = get_tool_context()
        engine = ctx.engine
        if not engine.has_graph(workflow_id):
            return
        graph = engine.get_graph(workflow_id)

        goal_analysis = self.get_latest_event_payload(workflow_id, EventType.GOAL_ANALYZED)
        scenario_hint = (goal_analysis.get("extracted_entities") or {}).get("scenario")

        for step_id in event.payload.get("ready_steps", []):
            try:
                step = graph.get_step(step_id)
            except KeyError:
                continue
            service = step.id

            checklist_result = invoke_tool(
                "retrieve_rules",
                {"query": f"required documents for {service}", "service": service, "top_k": 5},
                workflow_id=workflow_id,
            )
            required_docs = [r.requirement for r in checklist_result.rules]

            provided_docs = [] if scenario_hint == "document_missing" else list(required_docs)
            validation_payload = {"documents": provided_docs, "required_documents": required_docs}
            if scenario_hint:
                validation_payload["scenario"] = scenario_hint
            validation = invoke_tool("validate_document", validation_payload, workflow_id=workflow_id)

            if validation.valid:
                self.audit(
                    workflow_id,
                    event=EventType.DOCUMENTS_VALIDATED.value,
                    decision=f"step={step_id} service={service} all {len(required_docs)} checklist items present",
                    tool="validate_document",
                    api_result=validation.model_dump(),
                )
                await self.publish(
                    workflow_id,
                    EventType.DOCUMENTS_VALIDATED,
                    {"step_id": step_id, "service": service, "checklist": required_docs},
                )
            else:
                self.audit(
                    workflow_id,
                    event=EventType.DOCUMENT_MISSING.value,
                    decision=f"step={step_id} service={service} missing={validation.missing_documents}",
                    tool="validate_document",
                    api_result=validation.model_dump(),
                )
                await self.publish(
                    workflow_id,
                    EventType.DOCUMENT_MISSING,
                    {
                        "step_id": step_id,
                        "service": service,
                        "missing_documents": validation.missing_documents,
                        "reason": f"missing documents for {service}: {validation.missing_documents}",
                    },
                )
