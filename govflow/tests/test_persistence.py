from backend.models.audit import AuditLogEntry
from backend.models.enums import EventType, WorkflowStatus
from backend.models.event import Event
from backend.models.workflow import Workflow
from backend.services.sqlite_repo import (
    SQLiteAuditRepository,
    SQLiteEventRepository,
    SQLiteWorkflowRepository,
)


def test_workflow_create_update_read_roundtrip(temp_db):
    repo = SQLiteWorkflowRepository()

    workflow = Workflow(
        workflow_id="wf-persist-1",
        user_id="user-1",
        goal="start a food processing business",
        status=WorkflowStatus.RUNNING,
        pending_steps=["business_registration"],
    )
    repo.create(workflow)

    fetched = repo.get("wf-persist-1")
    assert fetched is not None
    assert fetched.workflow_id == workflow.workflow_id
    assert fetched.goal == workflow.goal
    assert fetched.status == WorkflowStatus.RUNNING

    fetched.status = WorkflowStatus.COMPLETED
    fetched.completed_steps = ["business_registration"]
    fetched.pending_steps = []
    repo.update(fetched)

    updated = repo.get("wf-persist-1")
    assert updated.status == WorkflowStatus.COMPLETED
    assert updated.completed_steps == ["business_registration"]


def test_workflow_list_filters_by_user(temp_db):
    repo = SQLiteWorkflowRepository()
    repo.create(Workflow(workflow_id="wf-a", user_id="user-a", goal="goal a"))
    repo.create(Workflow(workflow_id="wf-b", user_id="user-b", goal="goal b"))

    all_workflows = repo.list()
    assert len(all_workflows) == 2

    user_a_workflows = repo.list(user_id="user-a")
    assert len(user_a_workflows) == 1
    assert user_a_workflows[0].workflow_id == "wf-a"


def test_workflow_get_missing_returns_none(temp_db):
    repo = SQLiteWorkflowRepository()
    assert repo.get("does-not-exist") is None


def test_event_repository_append_and_list(temp_db):
    repo = SQLiteEventRepository()
    event = Event(workflow_id="wf-1", event_type=EventType.WORKFLOW_CREATED, payload={"goal": "test"})
    repo.append(event)

    events = repo.list_for_workflow("wf-1")
    assert len(events) == 1
    assert events[0].event_id == event.event_id
    assert events[0].event_type == EventType.WORKFLOW_CREATED


def test_audit_repository_append_and_list(temp_db):
    repo = SQLiteAuditRepository()
    entry = AuditLogEntry(
        workflow_id="wf-1",
        event="WORKFLOW_CREATED",
        agent="workflow_engine",
        decision="created workflow from template",
        source="system",
    )
    repo.append(entry)

    entries = repo.list_for_workflow("wf-1")
    assert len(entries) == 1
    assert entries[0].agent == "workflow_engine"
