"""Hardcoded demo workflow template.

Part 1 has no LLM planning, so this is the one concrete workflow the
engine drives through its states end-to-end: registering a small
food-processing business.

Part 2's Workflow Planner Agent will replace this hardcoded template with
a dynamically generated one -- callers should treat this as a fallback /
default rather than the only path forward.
"""

from __future__ import annotations

from backend.models.workflow import WorkflowStep

FOOD_PROCESSING_BUSINESS_TEMPLATE = "food_processing_business"


def build_food_processing_business_steps() -> list[WorkflowStep]:
    """business_registration -> {tax_registration, food_license} -> local_approval"""
    return [
        WorkflowStep(
            id="business_registration",
            name="Business Registration",
            service="business-registration",
            depends_on=[],
        ),
        WorkflowStep(
            id="tax_registration",
            name="Tax Registration",
            service="tax-registration",
            depends_on=["business_registration"],
        ),
        WorkflowStep(
            id="food_license",
            name="Food License",
            service="food-license",
            depends_on=["business_registration"],
        ),
        WorkflowStep(
            id="local_approval",
            name="Local Approval",
            service="local-approval",
            depends_on=["tax_registration", "food_license"],
        ),
    ]


def get_template(name: str) -> list[WorkflowStep]:
    if name == FOOD_PROCESSING_BUSINESS_TEMPLATE:
        return build_food_processing_business_steps()
    raise ValueError(f"unknown workflow template {name!r}")
