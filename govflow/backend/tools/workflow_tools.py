"""Tools wrapping the Part 1 persistence layer (workflow + audit repos)."""

from __future__ import annotations

from typing import Any, Dict

from backend.models.audit import AuditLogEntry
from backend.tools.context import get_tool_context
from backend.tools.registry import register_tool
from backend.tools.schemas import (
    AppendAuditEntryInput,
    AuditAppendResult,
    UpdateWorkflowStateInput,
    WorkflowStateResult,
)

# Fields on Workflow that agents are allowed to patch via update_workflow_state.
# Deliberately excludes workflow_id/created_at (immutable identity) and
# status/current_step/completed_steps/pending_steps/failed_steps, which are
# owned by WorkflowGraph + WorkflowEngine, not by ad-hoc agent patches --
# an agent that needs to change step status goes through the engine
# (complete_step/fail_step/block_step), not this tool.
_PATCHABLE_FIELDS = {"required_documents", "applications", "events"}


@register_tool(
    "update_workflow_state",
    UpdateWorkflowStateInput,
    WorkflowStateResult,
    description="Applies a patch to allowlisted Workflow fields (required_documents, applications, events).",
    rate_limited=False,
)
def update_workflow_state(data: UpdateWorkflowStateInput) -> WorkflowStateResult:
    ctx = get_tool_context()
    workflow = ctx.workflow_repo.get(data.workflow_id)
    if workflow is None:
        raise ValueError(f"workflow {data.workflow_id!r} not found")

    rejected_keys = set(data.patch) - _PATCHABLE_FIELDS
    if rejected_keys:
        raise ValueError(
            f"update_workflow_state cannot patch {sorted(rejected_keys)}; "
            f"only {sorted(_PATCHABLE_FIELDS)} are agent-writable. Step/status "
            "changes must go through WorkflowEngine."
        )

    for key, value in data.patch.items():
        setattr(workflow, key, value)
    ctx.workflow_repo.update(workflow)

    return WorkflowStateResult(
        workflow_id=workflow.workflow_id,
        status=workflow.status.value,
        current_step=workflow.current_step,
        completed_steps=workflow.completed_steps,
        pending_steps=workflow.pending_steps,
        failed_steps=workflow.failed_steps,
    )


@register_tool(
    "append_audit_entry",
    AppendAuditEntryInput,
    AuditAppendResult,
    description="Appends an entry to the audit trail for a workflow.",
    rate_limited=False,
)
def append_audit_entry(data: AppendAuditEntryInput) -> AuditAppendResult:
    ctx = get_tool_context()
    entry = AuditLogEntry(
        workflow_id=data.workflow_id,
        event=data.event,
        agent=data.agent,
        decision=data.decision,
        source=data.source,
        tool=data.tool,
        api_result=data.api_result,
        state_transition=data.state_transition,
    )
    ctx.audit_repo.append(entry)
    return AuditAppendResult(recorded=True)
