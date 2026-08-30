"""Service catalog, sourced from the systems agents actually use.

Added in Part 3 for GET /api/services. Deliberately NOT a separately
maintained hardcoded list: the service names + tool routing come from
DepartmentRouterAgent.SERVICE_TOOL_MAP (the same table that actually
drives routing), the department names come from
mock_services.client.SERVICE_DEPARTMENTS (the same table the mock APIs
actually use), and the description is pulled live from the RAG knowledge
base via the same retriever RegulationAgent/EligibilityAgent/DocumentAgent
use -- so this endpoint can never drift out of sync with what the agents
actually do.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel

from backend.agents.department_router import SERVICE_TOOL_MAP
from backend.rag.retriever import retrieve
from mock_services.client import SERVICE_DEPARTMENTS


class ServiceInfo(BaseModel):
    service: str
    department: str
    tool_name: str
    description: str
    mock_data: bool = True


def get_service_catalog() -> List[ServiceInfo]:
    catalog: List[ServiceInfo] = []
    for service, tool_name in SERVICE_TOOL_MAP.items():
        hyphenated = service.replace("_", "-")
        department = SERVICE_DEPARTMENTS.get(hyphenated, "Unknown Department (Mock)")

        results = retrieve(f"{service} overview requirements", top_k=1, service=service)
        description = results[0].requirement if results else f"No knowledge-base overview found for {service}."

        catalog.append(
            ServiceInfo(
                service=service,
                department=department,
                tool_name=tool_name,
                description=description,
            )
        )
    return catalog
