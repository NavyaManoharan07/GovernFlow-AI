"""Pydantic response schemas for every Gemini structured-output call.

Passed directly as ``response_schema`` to GeminiClient.generate_structured
-- one schema per agent decision, so every LLM call in the system returns
a validated instance of one of these, never raw text.

IMPORTANT: no field here may be a generic ``dict``/``Dict[str, Any]`` (or
any other open-ended-keys mapping). Pydantic renders that as a JSON Schema
object with ``additionalProperties``, which the plain Gemini Developer API
(an `ai.google.dev` API key, not Vertex AI / Gemini Enterprise) rejects
outright for structured output: "additionalProperties is only supported in
Gemini Enterprise Agent Platform mode, not in Gemini Developer API mode."
Every field below is therefore either a primitive, a list of primitives,
or a nested model with a fixed, named set of fields -- never a free-form
mapping.
"""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class ExtractedEntities(BaseModel):
    """Fixed, named fields instead of a free-form dict -- see the module
    docstring for why. Covers the small set of entities a business-goal
    sentence realistically yields; anything not stated is left null
    rather than guessed (GoalInterpreterAgent's system prompt says so
    explicitly).

    ``scenario`` is not something the prompt asks Gemini to extract from
    real goal text -- it's a demo/test-only hook (also settable directly
    when constructing GoalAnalysis in tests, or overridden by the
    authoritative Workflow.metadata["scenario"] the Part 3 demo
    orchestrator sets -- see ApplicationAgent) that a real Gemini call
    will simply leave null.
    """

    business_name: str | None = None
    location_detail: str | None = None
    employee_count: int | None = None
    annual_turnover: float | None = None
    product_type: str | None = None
    scenario: str | None = None


class GoalAnalysis(BaseModel):
    goal: str
    location: str | None = None
    business_type: str | None = None
    required_workflow: bool
    extracted_entities: ExtractedEntities = Field(default_factory=ExtractedEntities)
    missing_info: List[str] = Field(default_factory=list)


class ServiceDependencies(BaseModel):
    """service -> list of prerequisite services, one fixed field per
    catalog service (see WorkflowPlannerAgent.CATALOG) instead of an
    open-ended dict, for the same reason as ExtractedEntities above.
    Every field defaults to an empty list ("no prerequisites"/"service not
    selected"); WorkflowPlannerAgent only looks at the fields for services
    it actually selected."""

    business_registration: List[str] = Field(default_factory=list)
    tax_registration: List[str] = Field(default_factory=list)
    food_license: List[str] = Field(default_factory=list)
    local_approval: List[str] = Field(default_factory=list)


class ServicePlan(BaseModel):
    services: List[str] = Field(
        description="Subset of business_registration, tax_registration, food_license, local_approval"
    )
    dependencies: ServiceDependencies = Field(default_factory=ServiceDependencies)
    reasoning: str


class EligibilityResult(BaseModel):
    status: Literal["eligible", "ineligible", "needs_information"]
    missing_fields: List[str] = Field(default_factory=list)
    reasoning: str
