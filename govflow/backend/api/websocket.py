"""WebSocket activity stream: WS /ws/workflows/{workflow_id}.

ConnectionManager registers ONE handler directly on the live EventBus via
``event_bus.subscribe_all(...)`` (bypassing the declarative
backend.events.registry / with_retry wrapping on purpose -- a broadcast
failure must never publish a WORKFLOW_FAILED event or retry anything, it
should just log and move on). From that single hook it derives all four
message envelope types:

  - "event": the published Event itself (type, payload, source_agent).
  - "agent_activity": the same Event reframed as "agent X did Y" -- the
    event *is* the agent activity record in this system, so no separate
    tracking is needed.
  - "state_change": broadcast only when workflow.status actually differs
    from the last value seen for that workflow_id (re-reads the
    persisted Workflow after every event). Because WorkflowEngine's own
    core handlers (backend/workflows/engine.py) run as ordinary
    registered handlers concurrently with this one, a status change
    triggered by the SAME event this hook is processing may not be
    persisted yet -- it will reliably be caught on the very next event
    instead (the engine always publishes a follow-up event --
    NEXT_ACTION_TRIGGERED, WORKFLOW_COMPLETED, or USER_ACTION_REQUIRED --
    whenever it changes workflow status), so nothing is ever missed, at
    most delayed by one hop (sub-millisecond in practice).
  - "audit": diffed against the audit repository's entry count for that
    workflow_id, broadcasting only entries newer than the last check.
    Same one-hop-eventual-consistency caveat as state_change, for the
    same reason (AuditAgent's bus-wide write is itself a concurrent
    wildcard handler).

This design requires zero changes to Part 1/2's agents or engine.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.models.audit import AuditLogEntry
from backend.models.event import Event
from backend.services.interfaces import AuditRepository, EventRepository, WorkflowRepository

logger = logging.getLogger("govflow.api.websocket")

router = APIRouter()


def _envelope(msg_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": msg_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


def _event_payload(event: Event) -> Dict[str, Any]:
    return {
        "event_id": event.event_id,
        "workflow_id": event.workflow_id,
        "event_type": event.event_type.value,
        "source_agent": event.source_agent,
        "payload": event.payload,
        "timestamp": event.timestamp.isoformat(),
    }


def _agent_activity_payload(event: Event) -> Dict[str, Any]:
    return {
        "workflow_id": event.workflow_id,
        "agent": event.source_agent,
        "action": event.event_type.value,
        "timestamp": event.timestamp.isoformat(),
    }


def _audit_payload(entry: AuditLogEntry) -> Dict[str, Any]:
    return {
        "workflow_id": entry.workflow_id,
        "timestamp": entry.timestamp.isoformat(),
        "event": entry.event,
        "agent": entry.agent,
        "decision": entry.decision,
        "source": entry.source,
        "tool": entry.tool,
        "api_result": entry.api_result,
    }


def _state_payload(workflow) -> Dict[str, Any]:
    return {
        "workflow_id": workflow.workflow_id,
        "status": workflow.status.value,
        "current_step": workflow.current_step,
        "completed_steps": workflow.completed_steps,
        "pending_steps": workflow.pending_steps,
        "failed_steps": workflow.failed_steps,
    }


class ConnectionManager:
    def __init__(
        self,
        workflow_repo: WorkflowRepository,
        event_repo: EventRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self.workflow_repo = workflow_repo
        self.event_repo = event_repo
        self.audit_repo = audit_repo
        self._connections: Dict[str, List[WebSocket]] = defaultdict(list)
        self._last_status: Dict[str, str] = {}
        self._last_event_count: Dict[str, int] = {}
        self._last_audit_count: Dict[str, int] = {}
        # Guards each workflow_id's "read repo -> diff against last-seen
        # cursor -> broadcast -> advance cursor" critical section. Without
        # this, a socket connecting (snapshot: reads full history, then
        # registers for live updates) can race with a concurrently
        # published event's on_event() callback: the new event can end up
        # in both the snapshot's history read AND a live broadcast,
        # duplicating it on that one client. The lock makes "how many
        # events/audit entries has this workflow_id already had broadcast"
        # a single, atomically-advanced cursor shared by both paths.
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def connect(self, workflow_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._locks[workflow_id]:
            self._connections[workflow_id].append(websocket)
            await self._send_snapshot_locked(workflow_id, websocket)

    def disconnect(self, workflow_id: str, websocket: WebSocket) -> None:
        sockets = self._connections.get(workflow_id)
        if sockets and websocket in sockets:
            sockets.remove(websocket)

    async def _send_snapshot_locked(self, workflow_id: str, websocket: WebSocket) -> None:
        """On-connect replay: every historical event, every historical
        audit entry, then one state_change with current workflow state --
        so a client connecting mid-workflow isn't lost. Uses the same
        message types as live updates (per the spec'd 4-type envelope
        contract) rather than inventing a separate "snapshot" type.

        Must be called while holding self._locks[workflow_id] -- advances
        the same cursors on_event() reads, which is what prevents the
        duplicate-delivery race described above."""
        try:
            events = self.event_repo.list_for_workflow(workflow_id)
            for event in events:
                await websocket.send_json(_envelope("event", _event_payload(event)))
                await websocket.send_json(_envelope("agent_activity", _agent_activity_payload(event)))
            self._last_event_count[workflow_id] = len(events)

            audits = self.audit_repo.list_for_workflow(workflow_id)
            for entry in audits:
                await websocket.send_json(_envelope("audit", _audit_payload(entry)))
            self._last_audit_count[workflow_id] = len(audits)

            workflow = self.workflow_repo.get(workflow_id)
            if workflow is not None:
                await websocket.send_json(_envelope("state_change", _state_payload(workflow)))
                self._last_status[workflow_id] = workflow.status.value
        except Exception:
            logger.exception("failed sending WS snapshot for workflow=%s", workflow_id)

    async def broadcast(self, workflow_id: str, message: Dict[str, Any]) -> None:
        sockets = list(self._connections.get(workflow_id, []))
        dead: List[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(workflow_id, ws)

    async def on_event(self, event: Event) -> None:
        """Registered directly on EventBus.subscribe_all -- must never
        raise (a broadcast failure must not affect the workflow itself).

        Diffs against the same event/audit-count cursors _send_snapshot_locked
        advances, rather than assuming "this callback = exactly one new
        event to broadcast" -- multiple events can legitimately queue up
        between two callback invocations (e.g. while a lock is held), and
        this makes each event/audit entry get broadcast exactly once
        regardless of timing."""
        workflow_id = event.workflow_id
        if not self._connections.get(workflow_id):
            return  # no one listening -- skip the repo reads too

        async with self._locks[workflow_id]:
            try:
                events = self.event_repo.list_for_workflow(workflow_id)
                last_event_count = self._last_event_count.get(workflow_id, 0)
                for e in events[last_event_count:]:
                    await self.broadcast(workflow_id, _envelope("event", _event_payload(e)))
                    await self.broadcast(workflow_id, _envelope("agent_activity", _agent_activity_payload(e)))
                self._last_event_count[workflow_id] = len(events)

                audits = self.audit_repo.list_for_workflow(workflow_id)
                last_audit_count = self._last_audit_count.get(workflow_id, 0)
                for entry in audits[last_audit_count:]:
                    await self.broadcast(workflow_id, _envelope("audit", _audit_payload(entry)))
                self._last_audit_count[workflow_id] = len(audits)

                workflow = self.workflow_repo.get(workflow_id)
                if workflow is not None:
                    new_status = workflow.status.value
                    if self._last_status.get(workflow_id) != new_status:
                        self._last_status[workflow_id] = new_status
                        await self.broadcast(workflow_id, _envelope("state_change", _state_payload(workflow)))
            except Exception:
                logger.exception("WS broadcast failed for workflow=%s event=%s", workflow_id, event.event_type)


@router.websocket("/ws/workflows/{workflow_id}")
async def workflow_activity_stream(websocket: WebSocket, workflow_id: str) -> None:
    manager: ConnectionManager = websocket.app.state.connection_manager
    await manager.connect(workflow_id, websocket)
    try:
        while True:
            # This is a server-push stream; we don't expect client
            # messages, but we must keep receiving to detect disconnects
            # (and tolerate a client sending pings/keepalives).
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(workflow_id, websocket)
    except Exception:
        logger.exception("WS connection error for workflow=%s", workflow_id)
        manager.disconnect(workflow_id, websocket)
