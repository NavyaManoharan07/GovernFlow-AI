"""Pydantic input/output schemas for every registered tool.

Every tool in backend/tools/ has a strict input schema and output schema.
Agents never call a tool with a raw dict or receive raw unstructured text
back -- ToolRegistry.invoke() validates both directions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.rag.schemas import RetrievedRule

# Re-exported so tool modules only need to import from here.
__all__ = [
    "RetrievedRule",
    "ApplicationSubmitInput",
    "ApplicationResult",
    "StatusCheckInput",
    "StatusResult",
    "DocumentValidationInput",
    "ValidationResult",
    "RetrieveRulesInput",
    "RetrieveRulesResult",
    "UpdateWorkflowStateInput",
    "WorkflowStateResult",
    "AppendAuditEntryInput",
    "AuditAppendResult",
]


class ApplicationSubmitInput(BaseModel):
    business_name: str
    applicant_name: Optional[str] = None
    scenario: Optional[str] = None
    extra_fields: Dict[str, Any] = Field(default_factory=dict)


class ApplicationResult(BaseModel):
    application_id: str
    service: str
    department: str
    status: str
    scenario: str
    mock_data: bool = True


class StatusCheckInput(BaseModel):
    application_id: str = Field(min_length=1)


class StatusResult(BaseModel):
    application_id: str
    service: Optional[str] = None
    department: Optional[str] = None
    status: str
    poll_count: int = 0
    mock_data: bool = True


class DocumentValidationInput(BaseModel):
    documents: List[str] = Field(default_factory=list)
    required_documents: List[str] = Field(default_factory=list)
    scenario: Optional[str] = None


class ValidationResult(BaseModel):
    valid: bool
    missing_documents: List[str] = Field(default_factory=list)
    validated_documents: List[str] = Field(default_factory=list)
    mock_data: bool = True


class RetrieveRulesInput(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    service: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20)


class RetrieveRulesResult(BaseModel):
    rules: List[RetrievedRule]


class UpdateWorkflowStateInput(BaseModel):
    workflow_id: str = Field(min_length=1)
    patch: Dict[str, Any] = Field(default_factory=dict)


class WorkflowStateResult(BaseModel):
    workflow_id: str
    status: str
    current_step: Optional[str] = None
    completed_steps: List[str] = Field(default_factory=list)
    pending_steps: List[str] = Field(default_factory=list)
    failed_steps: List[str] = Field(default_factory=list)


class AppendAuditEntryInput(BaseModel):
    workflow_id: str = Field(min_length=1)
    event: str
    agent: str
    decision: str
    source: str = "agent"
    tool: Optional[str] = None
    api_result: Optional[Dict[str, Any]] = None
    state_transition: Optional[Dict[str, Any]] = None


class AuditAppendResult(BaseModel):
    recorded: bool = True
