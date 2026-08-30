"""FastAPI router for mock government APIs.

Mounted into the main app under /mock. Routes are thin wrappers around
GovernmentAPIClient (mock_services/client.py) -- they do not implement
business logic themselves, so a real integration can later be swapped in
behind the same client interface.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from mock_services.client import MockGovernmentAPIClient, TransientAPIError, get_mock_client

router = APIRouter(prefix="/mock", tags=["mock-government-apis"])


def _client() -> MockGovernmentAPIClient:
    return get_mock_client()


@router.post("/business-registration")
async def business_registration(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _client().submit_business_registration(payload)


@router.post("/tax-registration")
async def tax_registration(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _client().submit_tax_registration(payload)


@router.post("/food-license")
async def food_license(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _client().submit_food_license(payload)


@router.post("/local-approval")
async def local_approval(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _client().submit_local_approval(payload)


@router.get("/application/{application_id}")
async def get_application(application_id: str) -> Dict[str, Any]:
    try:
        return _client().get_application_status(application_id)
    except TransientAPIError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": str(exc),
                "MOCK_DATA": True,
                "note": "Simulated transient failure. Retry the request.",
            },
        )


@router.post("/document-validation")
async def document_validation(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _client().validate_documents(payload)
