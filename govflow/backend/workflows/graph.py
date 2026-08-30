"""WorkflowGraph: a DAG of WorkflowStep objects with dependency logic."""

from __future__ import annotations

from typing import Dict, List

from backend.models.enums import StepStatus
from backend.models.workflow import WorkflowStep


class WorkflowGraph:
    """Represents workflow steps and their dependencies as a DAG."""

    def __init__(self, steps: List[WorkflowStep]) -> None:
        self._steps: Dict[str, WorkflowStep] = {step.id: step for step in steps}
        self._validate_dag()

    def _validate_dag(self) -> None:
        for step in self._steps.values():
            for dep in step.depends_on:
                if dep not in self._steps:
                    raise ValueError(f"step {step.id!r} depends on unknown step {dep!r}")
        if self._has_cycle():
            raise ValueError("WorkflowGraph contains a dependency cycle")

    def _has_cycle(self) -> bool:
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {step_id: WHITE for step_id in self._steps}

        def visit(step_id: str) -> bool:
            color[step_id] = GRAY
            for dep in self._steps[step_id].depends_on:
                if color[dep] == GRAY:
                    return True
                if color[dep] == WHITE and visit(dep):
                    return True
            color[step_id] = BLACK
            return False

        return any(color[step_id] == WHITE and visit(step_id) for step_id in self._steps)

    def get_step(self, step_id: str) -> WorkflowStep:
        return self._steps[step_id]

    def all_steps(self) -> List[WorkflowStep]:
        return list(self._steps.values())

    def get_ready_steps(self) -> List[WorkflowStep]:
        """Steps that are PENDING and whose dependencies are all COMPLETED."""
        ready = []
        for step in self._steps.values():
            if step.status != StepStatus.PENDING:
                continue
            if all(self._steps[dep].status == StepStatus.COMPLETED for dep in step.depends_on):
                ready.append(step)
        return ready

    def mark_step_status(self, step_id: str, status: StepStatus) -> None:
        if step_id not in self._steps:
            raise KeyError(f"unknown step_id {step_id!r}")
        self._steps[step_id].status = status

    def claim_ready_steps(self) -> List[WorkflowStep]:
        """Atomically (no await in between) computes the ready steps AND
        marks them RUNNING before returning them.

        Added in Part 2: without this, ``get_ready_steps()`` keeps
        returning a step as "ready" for as long as its status stays
        PENDING -- which it would, for the entire submit/poll lifecycle,
        since only complete_step/fail_step/block_step change status. Any
        *other* sibling step completing concurrently (a very real
        scenario once StatusMonitorAgent runs multiple independent
        asyncio polling loops) would recompute ready steps, see the
        still-PENDING in-flight step as "ready" again, and cause it to be
        dispatched/submitted a second time. Claiming closes that window.
        """
        ready = self.get_ready_steps()
        for step in ready:
            self.mark_step_status(step.id, StepStatus.RUNNING)
        return ready

    def active_step_ids(self) -> List[str]:
        """PENDING or RUNNING -- i.e. not yet completed/failed/blocked.
        Used for Workflow.pending_steps so in-flight (RUNNING) steps stay
        visible to external consumers instead of disappearing from every
        status list the moment they're claimed."""
        return [s.id for s in self._steps.values() if s.status in (StepStatus.PENDING, StepStatus.RUNNING)]

    def is_complete(self) -> bool:
        return all(step.status == StepStatus.COMPLETED for step in self._steps.values())

    def has_failed_blocking_step(self) -> bool:
        """True if any step is FAILED or BLOCKED, which halts downstream progress."""
        return any(step.status in (StepStatus.FAILED, StepStatus.BLOCKED) for step in self._steps.values())

    def completed_step_ids(self) -> List[str]:
        return [s.id for s in self._steps.values() if s.status == StepStatus.COMPLETED]

    def pending_step_ids(self) -> List[str]:
        return [s.id for s in self._steps.values() if s.status == StepStatus.PENDING]

    def failed_step_ids(self) -> List[str]:
        return [s.id for s in self._steps.values() if s.status == StepStatus.FAILED]

    def blocked_step_ids(self) -> List[str]:
        return [s.id for s in self._steps.values() if s.status == StepStatus.BLOCKED]
