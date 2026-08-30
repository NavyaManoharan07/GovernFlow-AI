"""GovernmentAPIClient protocol + mock implementation.

The router (mock_services/router.py) calls into a GovernmentAPIClient
implementation rather than embedding logic directly in the HTTP handlers.
This means a real integration can later implement the exact same method
signatures (RealGovernmentAPIClient) and be swapped in without touching
the routes or any application code that depends on the protocol.

Deterministic demo scenarios (so repeated demo runs are reliable) are
selected via an explicit `scenario` field in the request payload, or
inferred from the business/applicant name as a convenience:
  - "clean"              : SUBMITTED -> PENDING -> APPROVED
  - "document_missing"   : SUBMITTED -> DOCUMENT_MISSING (stays)
  - "rejected"            : SUBMITTED -> PENDING -> REJECTED
  - "transient_failure"  : SUBMITTED -> (poll 1 raises transient error) -> APPROVED
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol

SCENARIO_CLEAN = "clean"
SCENARIO_DOCUMENT_MISSING = "document_missing"
SCENARIO_REJECTED = "rejected"
SCENARIO_TRANSIENT_FAILURE = "transient_failure"

_VALID_SCENARIOS = {
    SCENARIO_CLEAN,
    SCENARIO_DOCUMENT_MISSING,
    SCENARIO_REJECTED,
    SCENARIO_TRANSIENT_FAILURE,
}

_NAME_SCENARIO_HINTS = {
    "missingdocs": SCENARIO_DOCUMENT_MISSING,
    "reject": SCENARIO_REJECTED,
    "retry": SCENARIO_TRANSIENT_FAILURE,
    "transient": SCENARIO_TRANSIENT_FAILURE,
}

# Added in Part 3: a static service -> department lookup, so GET
# /api/services can build the service catalog without instantiating a fake
# application just to read the department name back out of a submit
# response. Keyed by the same hyphenated service string WorkflowStep.service
# and the mock router's URL segments use.
SERVICE_DEPARTMENTS: Dict[str, str] = {
    "business-registration": "Ministry of Corporate Affairs (Mock)",
    "tax-registration": "Tax Department (Mock)",
    "food-license": "Food Safety Authority (Mock)",
    "local-approval": "Local Municipal Authority (Mock)",
}


class TransientAPIError(Exception):
    """Raised by the mock client to simulate a transient upstream failure."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _infer_scenario(payload: Dict[str, Any]) -> str:
    explicit = payload.get("scenario")
    if explicit in _VALID_SCENARIOS:
        return explicit

    name_fields = " ".join(
        str(payload.get(field, "")) for field in ("business_name", "applicant_name", "name")
    ).lower()
    for hint, scenario in _NAME_SCENARIO_HINTS.items():
        if hint in name_fields:
            return scenario
    return SCENARIO_CLEAN


class GovernmentAPIClient(Protocol):
    """Interface a real government integration would implement."""

    def submit_business_registration(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...

    def submit_tax_registration(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...

    def submit_food_license(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...

    def submit_local_approval(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...

    def get_application_status(self, application_id: str) -> Dict[str, Any]: ...

    def validate_documents(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...


class MockGovernmentAPIClient:
    """In-memory mock implementation of GovernmentAPIClient.

    NOT a real government integration. All responses are clearly labeled
    MOCK_DATA=true. State is process-local and resets on restart.
    """

    def __init__(self) -> None:
        self._applications: Dict[str, Dict[str, Any]] = {}

    def _submit(self, service: str, department: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        application_id = str(uuid.uuid4())
        scenario = _infer_scenario(payload)
        self._applications[application_id] = {
            "application_id": application_id,
            "service": service,
            "department": department,
            "scenario": scenario,
            "status": "SUBMITTED",
            "poll_count": 0,
            "payload": payload,
            "submitted_at": _utcnow(),
        }
        return {
            "application_id": application_id,
            "service": service,
            "department": department,
            "status": "SUBMITTED",
            "scenario": scenario,
            "MOCK_DATA": True,
            "note": "This is a simulated response and does not represent a real government integration.",
        }

    def submit_business_registration(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._submit("business-registration", SERVICE_DEPARTMENTS["business-registration"], payload)

    def submit_tax_registration(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._submit("tax-registration", SERVICE_DEPARTMENTS["tax-registration"], payload)

    def submit_food_license(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._submit("food-license", SERVICE_DEPARTMENTS["food-license"], payload)

    def submit_local_approval(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._submit("local-approval", SERVICE_DEPARTMENTS["local-approval"], payload)

    def get_application_status(self, application_id: str) -> Dict[str, Any]:
        record = self._applications.get(application_id)
        if record is None:
            return {
                "application_id": application_id,
                "status": "NOT_FOUND",
                "MOCK_DATA": True,
                "note": "This is a simulated response and does not represent a real government integration.",
            }

        record["poll_count"] += 1
        poll_count = record["poll_count"]
        scenario = record["scenario"]

        if scenario == SCENARIO_CLEAN:
            status = "PENDING" if poll_count == 1 else "APPROVED"
        elif scenario == SCENARIO_DOCUMENT_MISSING:
            status = "DOCUMENT_MISSING"
        elif scenario == SCENARIO_REJECTED:
            status = "PENDING" if poll_count == 1 else "REJECTED"
        elif scenario == SCENARIO_TRANSIENT_FAILURE:
            if poll_count == 1:
                raise TransientAPIError(
                    f"simulated transient upstream failure for application_id={application_id}"
                )
            status = "APPROVED"
        else:
            status = "PENDING"

        record["status"] = status
        return {
            "application_id": application_id,
            "service": record["service"],
            "department": record["department"],
            "status": status,
            "scenario": scenario,
            "poll_count": poll_count,
            "MOCK_DATA": True,
            "note": "This is a simulated response and does not represent a real government integration.",
        }

    def validate_documents(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        documents = payload.get("documents", [])
        scenario = _infer_scenario(payload)
        if scenario == SCENARIO_DOCUMENT_MISSING or not documents:
            return {
                "valid": False,
                "missing_documents": payload.get("required_documents", ["proof_of_identity"]),
                "MOCK_DATA": True,
                "note": "This is a simulated response and does not represent a real government integration.",
            }
        return {
            "valid": True,
            "missing_documents": [],
            "validated_documents": documents,
            "MOCK_DATA": True,
            "note": "This is a simulated response and does not represent a real government integration.",
        }


_default_client: Optional[MockGovernmentAPIClient] = None


def get_mock_client() -> MockGovernmentAPIClient:
    global _default_client
    if _default_client is None:
        _default_client = MockGovernmentAPIClient()
    return _default_client


def reset_mock_client() -> None:
    """Test helper: resets in-memory application state."""
    global _default_client
    _default_client = None
