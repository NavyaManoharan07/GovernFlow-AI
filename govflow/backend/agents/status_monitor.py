"""StatusMonitorAgent: polls application status via a real asyncio
background task and reacts to status changes.

No LLM call -- status-to-event mapping is a fixed, deterministic table.
Each polling loop is a genuine asyncio.Task scheduled by handle() and
awaited independently in the background; handle() itself returns
immediately after scheduling so it doesn't block the event bus's
dispatch (a poll can take several intervals to resolve). wait_all() lets
tests/manual triggers deterministically wait for polling to finish instead
of guessing a sleep duration.
"""

from __future__ import annotations

import asyncio
import logging
import os

from backend.agents.base import Agent
from backend.models.enums import EventType
from backend.models.event import Event
from backend.tools.registry import invoke_tool

logger = logging.getLogger("govflow.agents.status_monitor")


class StatusMonitorAgent(Agent):
    def __init__(self) -> None:
        super().__init__("StatusMonitorAgent", "Polls application status and reacts to approval/rejection/missing documents")
        self.poll_interval_seconds = float(os.environ.get("STATUS_POLL_INTERVAL_SECONDS", "2"))
        self.max_polls = int(os.environ.get("STATUS_MAX_POLLS", "10"))
        self._tasks: dict[str, asyncio.Task] = {}

    async def handle(self, event: Event) -> None:
        if event.event_type != EventType.APPLICATION_SUBMITTED:
            return

        workflow_id = event.workflow_id
        step_id = event.payload["step_id"]
        application_id = event.payload["application_id"]

        task = asyncio.create_task(self._poll_loop(workflow_id, step_id, application_id))
        self._tasks[application_id] = task
        task.add_done_callback(lambda t, aid=application_id: self._tasks.pop(aid, None))

    async def wait_all(self, timeout: float = 30.0) -> None:
        """Test/manual-trigger helper: waits for every polling task that is
        in flight *right now* to finish (or the timeout to elapse). Note
        this is a one-shot snapshot -- a task's completion can itself
        trigger new poll tasks (e.g. approving one step makes its sibling
        steps ready, which get submitted and start their own polling), so
        after a workflow with multiple steps this may return before the
        whole cascade is done. Use ``wait_until_idle`` to wait for the
        entire cascade instead."""
        tasks = [t for t in self._tasks.values() if not t.done()]
        if tasks:
            await asyncio.wait(tasks, timeout=timeout)

    async def wait_until_idle(self, timeout: float = 30.0, check_interval: float = 0.05) -> bool:
        """Waits until no polling tasks are in flight, including ones
        spawned *during* the wait (as later steps become ready and get
        submitted). Returns True if it went idle before the timeout,
        False otherwise. This is what tests and the manual e2e trigger
        should use to know the autonomous cascade has fully settled."""
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            if not self._tasks:
                return True
            in_flight = [t for t in self._tasks.values() if not t.done()]
            if in_flight:
                await asyncio.wait(in_flight, timeout=check_interval)
            else:
                await asyncio.sleep(check_interval)
        return not self._tasks

    async def _poll_loop(self, workflow_id: str, step_id: str, application_id: str) -> None:
        last_status = None
        for attempt in range(self.max_polls):
            try:
                result = invoke_tool(
                    "check_application_status", {"application_id": application_id}, workflow_id=workflow_id
                )
            except Exception as exc:
                logger.info(
                    "status poll %d/%d transient failure for application=%s: %s -- retrying",
                    attempt + 1,
                    self.max_polls,
                    application_id,
                    exc,
                )
                await asyncio.sleep(self.poll_interval_seconds)
                continue

            if result.status != last_status:
                last_status = result.status
                self.audit(
                    workflow_id,
                    event=EventType.APPLICATION_STATUS_CHANGED.value,
                    decision=f"application={application_id} step={step_id} status={result.status}",
                    tool="check_application_status",
                    api_result=result.model_dump(),
                )
                await self.publish(
                    workflow_id,
                    EventType.APPLICATION_STATUS_CHANGED,
                    {"step_id": step_id, "application_id": application_id, "status": result.status},
                )

                if result.status == "APPROVED":
                    await self.publish(
                        workflow_id, EventType.APPLICATION_APPROVED, {"step_id": step_id, "application_id": application_id}
                    )
                    return
                if result.status == "REJECTED":
                    await self.publish(
                        workflow_id,
                        EventType.APPLICATION_REJECTED,
                        {
                            "step_id": step_id,
                            "application_id": application_id,
                            "reason": "application rejected by mock government service",
                        },
                    )
                    return
                if result.status == "DOCUMENT_MISSING":
                    await self.publish(
                        workflow_id,
                        EventType.DOCUMENT_MISSING,
                        {
                            "step_id": step_id,
                            "application_id": application_id,
                            "reason": "additional documents requested during review",
                        },
                    )
                    return

            await asyncio.sleep(self.poll_interval_seconds)

        logger.warning(
            "status monitor exhausted %d polls for application=%s (workflow=%s) without reaching a terminal state",
            self.max_polls,
            application_id,
            workflow_id,
        )
