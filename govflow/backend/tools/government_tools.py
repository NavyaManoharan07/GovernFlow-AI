"""Tools wrapping the Part 1 mock government services.

Calls the underlying MockGovernmentAPIClient directly (mock_services.client)
rather than round-tripping through HTTP -- both mock_services and backend
run in the same process for this hackathon prototype, so an httpx call
would only add latency and a second failure mode for no benefit. The
GovernmentAPIClient protocol (mock_services/client.py) is still what makes
this swappable: a real integration would only need to satisfy that
protocol, and these tool functions would not need to change.
"""

from __future__ import annotations

from mock_services.client import TransientAPIError, get_mock_client
from backend.tools.registry import register_tool
from backend.tools.schemas import (
    ApplicationResult,
    ApplicationSubmitInput,
    DocumentValidationInput,
    StatusCheckInput,
    StatusResult,
    ValidationResult,
)


def _submit_payload(data: ApplicationSubmitInput) -> dict:
    payload = dict(data.extra_fields)
    payload["business_name"] = data.business_name
    if data.applicant_name:
        payload["applicant_name"] = data.applicant_name
    if data.scenario:
        payload["scenario"] = data.scenario
    return payload


def _to_application_result(raw: dict) -> ApplicationResult:
    return ApplicationResult(
        application_id=raw["application_id"],
        service=raw["service"],
        department=raw["department"],
        status=raw["status"],
        scenario=raw["scenario"],
        mock_data=raw.get("MOCK_DATA", True),
    )


@register_tool(
    "call_business_registration_api",
    ApplicationSubmitInput,
    ApplicationResult,
    description="Submits a business registration application to the mock government service.",
)
def call_business_registration_api(data: ApplicationSubmitInput) -> ApplicationResult:
    raw = get_mock_client().submit_business_registration(_submit_payload(data))
    return _to_application_result(raw)


@register_tool(
    "call_tax_registration_api",
    ApplicationSubmitInput,
    ApplicationResult,
    description="Submits a tax registration application to the mock government service.",
)
def call_tax_registration_api(data: ApplicationSubmitInput) -> ApplicationResult:
    raw = get_mock_client().submit_tax_registration(_submit_payload(data))
    return _to_application_result(raw)


@register_tool(
    "call_food_license_api",
    ApplicationSubmitInput,
    ApplicationResult,
    description="Submits a food license application to the mock government service.",
)
def call_food_license_api(data: ApplicationSubmitInput) -> ApplicationResult:
    raw = get_mock_client().submit_food_license(_submit_payload(data))
    return _to_application_result(raw)


@register_tool(
    "call_local_approval_api",
    ApplicationSubmitInput,
    ApplicationResult,
    description="Submits a local approval application to the mock government service.",
)
def call_local_approval_api(data: ApplicationSubmitInput) -> ApplicationResult:
    raw = get_mock_client().submit_local_approval(_submit_payload(data))
    return _to_application_result(raw)


@register_tool(
    "check_application_status",
    StatusCheckInput,
    StatusResult,
    description="Polls the mock government service for an application's current status.",
)
def check_application_status(data: StatusCheckInput) -> StatusResult:
    try:
        raw = get_mock_client().get_application_status(data.application_id)
    except TransientAPIError as exc:
        # Surfaces as a transient failure the caller (ApplicationAgent /
        # StatusMonitorAgent) should retry -- not a permanent rejection.
        raise RuntimeError(f"transient upstream failure: {exc}") from exc

    return StatusResult(
        application_id=raw["application_id"],
        service=raw.get("service"),
        department=raw.get("department"),
        status=raw["status"],
        poll_count=raw.get("poll_count", 0),
        mock_data=raw.get("MOCK_DATA", True),
    )


@register_tool(
    "validate_document",
    DocumentValidationInput,
    ValidationResult,
    description="Validates provided document metadata against required documents via the mock service.",
)
def validate_document(data: DocumentValidationInput) -> ValidationResult:
    payload = {
        "documents": data.documents,
        "required_documents": data.required_documents,
    }
    if data.scenario:
        payload["scenario"] = data.scenario
    raw = get_mock_client().validate_documents(payload)
    return ValidationResult(
        valid=raw["valid"],
        missing_documents=raw.get("missing_documents", []),
        validated_documents=raw.get("validated_documents", []),
        mock_data=raw.get("MOCK_DATA", True),
    )
