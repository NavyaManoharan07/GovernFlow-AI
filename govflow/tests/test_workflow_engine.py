import pytest

from backend.events.bus import InProcessEventBus
from backend.models.enums import StepStatus, WorkflowStatus
from backend.services.sqlite_repo import (
    SQLiteAuditRepository,
    SQLiteEventRepository,
    SQLiteWorkflowRepository,
)
from backend.workflows.engine import WorkflowEngine
from backend.workflows.graph import WorkflowGraph
from backend.workflows.templates import build_food_processing_business_steps


def test_demo_dag_ready_steps_progress_correctly():
    graph = WorkflowGraph(build_food_processing_business_steps())

    # Initially only business_registration has no dependencies.
    ready = {s.id for s in graph.get_ready_steps()}
    assert ready == {"business_registration"}
    assert not graph.is_complete()

    graph.mark_step_status("business_registration", StepStatus.COMPLETED)
    ready = {s.id for s in graph.get_ready_steps()}
    assert ready == {"tax_registration", "food_license"}
    assert not graph.is_complete()

    graph.mark_step_status("tax_registration", StepStatus.COMPLETED)
    # local_approval still blocked on food_license
    ready = {s.id for s in graph.get_ready_steps()}
    assert ready == {"food_license"}

    graph.mark_step_status("food_license", StepStatus.COMPLETED)
    ready = {s.id for s in graph.get_ready_steps()}
    assert ready == {"local_approval"}
    assert not graph.is_complete()

    graph.mark_step_status("local_approval", StepStatus.COMPLETED)
    assert graph.get_ready_steps() == []
    assert graph.is_complete()


def test_dag_rejects_cycles():
    from backend.models.workflow import WorkflowStep

    with pytest.raises(ValueError):
        WorkflowGraph(
            [
                WorkflowStep(id="a", name="A", service="a", depends_on=["b"]),
                WorkflowStep(id="b", name="B", service="b", depends_on=["a"]),
            ]
        )


def test_has_failed_blocking_step():
    graph = WorkflowGraph(build_food_processing_business_steps())
    assert not graph.has_failed_blocking_step()
    graph.mark_step_status("food_license", StepStatus.FAILED)
    assert graph.has_failed_blocking_step()


@pytest.mark.asyncio
async def test_workflow_engine_drives_demo_workflow_end_to_end(temp_db):
    bus = InProcessEventBus()
    workflow_repo = SQLiteWorkflowRepository()
    event_repo = SQLiteEventRepository()
    audit_repo = SQLiteAuditRepository()
    engine = WorkflowEngine(bus, workflow_repo, event_repo, audit_repo)

    workflow = await engine.create_workflow(user_id="user-1", goal="start a food processing business")
    assert workflow.status == WorkflowStatus.RUNNING
    assert workflow.current_step == "business_registration"

    workflow = await engine.complete_step(workflow.workflow_id, "business_registration")
    assert set(workflow.completed_steps) == {"business_registration"}
    assert workflow.current_step in {"tax_registration", "food_license"}

    workflow = await engine.complete_step(workflow.workflow_id, "tax_registration")
    workflow = await engine.complete_step(workflow.workflow_id, "food_license")
    assert workflow.current_step == "local_approval"

    workflow = await engine.complete_step(workflow.workflow_id, "local_approval")
    assert workflow.status == WorkflowStatus.COMPLETED
    assert set(workflow.completed_steps) == {
        "business_registration",
        "tax_registration",
        "food_license",
        "local_approval",
    }

    persisted = workflow_repo.get(workflow.workflow_id)
    assert persisted.status == WorkflowStatus.COMPLETED

    events = event_repo.list_for_workflow(workflow.workflow_id)
    event_types = [e.event_type for e in events]
    assert "WORKFLOW_CREATED" in [et.value for et in event_types]
    assert "WORKFLOW_COMPLETED" in [et.value for et in event_types]


@pytest.mark.asyncio
async def test_workflow_engine_fail_step(temp_db):
    bus = InProcessEventBus()
    workflow_repo = SQLiteWorkflowRepository()
    event_repo = SQLiteEventRepository()
    engine = WorkflowEngine(bus, workflow_repo, event_repo)

    workflow = await engine.create_workflow(user_id="user-1", goal="start a food processing business")
    workflow = await engine.fail_step(workflow.workflow_id, "business_registration", reason="rejected")

    assert workflow.status == WorkflowStatus.FAILED
    assert "business_registration" in workflow.failed_steps
