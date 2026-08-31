"""SQLite implementations of the repository interfaces. Fully working locally."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from backend.models.audit import AuditLogEntry
from backend.models.event import Event
from backend.models.notification import Notification
from backend.models.workflow import Workflow
from backend.services.db import get_connection
from backend.services.interfaces import (
    AuditRepository,
    EventRepository,
    NotificationRepository,
    WorkflowRepository,
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteWorkflowRepository(WorkflowRepository):
    def __init__(self, conn: Optional[sqlite3.Connection] = None) -> None:
        self._conn = conn

    def _get_conn(self) -> sqlite3.Connection:
        return self._conn if self._conn is not None else get_connection()

    def create(self, workflow: Workflow) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO workflows (workflow_id, user_id, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (
                workflow.workflow_id,
                workflow.user_id,
                workflow.model_dump_json(),
                workflow.created_at.isoformat(),
                workflow.updated_at.isoformat(),
            ),
        )
        conn.commit()

    def get(self, workflow_id: str) -> Optional[Workflow]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT data FROM workflows WHERE workflow_id = ?", (workflow_id,)
        ).fetchone()
        if row is None:
            return None
        return Workflow.model_validate_json(row["data"])

    def update(self, workflow: Workflow) -> None:
        conn = self._get_conn()
        workflow.updated_at = datetime.now(timezone.utc)
        cur = conn.execute(
            "UPDATE workflows SET data = ?, updated_at = ? WHERE workflow_id = ?",
            (workflow.model_dump_json(), workflow.updated_at.isoformat(), workflow.workflow_id),
        )
        if cur.rowcount == 0:
            raise KeyError(f"workflow {workflow.workflow_id!r} does not exist; call create() first")
        conn.commit()

    def list(self, user_id: Optional[str] = None) -> List[Workflow]:
        conn = self._get_conn()
        if user_id is not None:
            rows = conn.execute(
                "SELECT data FROM workflows WHERE user_id = ? ORDER BY created_at", (user_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT data FROM workflows ORDER BY created_at").fetchall()
        return [Workflow.model_validate_json(row["data"]) for row in rows]


class SQLiteEventRepository(EventRepository):
    def __init__(self, conn: Optional[sqlite3.Connection] = None) -> None:
        self._conn = conn

    def _get_conn(self) -> sqlite3.Connection:
        return self._conn if self._conn is not None else get_connection()

    def append(self, event: Event) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO events (event_id, workflow_id, event_type, data, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.workflow_id,
                event.event_type.value,
                event.model_dump_json(),
                event.timestamp.isoformat(),
            ),
        )
        conn.commit()

    def list_for_workflow(self, workflow_id: str) -> List[Event]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT data FROM events WHERE workflow_id = ? ORDER BY timestamp", (workflow_id,)
        ).fetchall()
        return [Event.model_validate_json(row["data"]) for row in rows]


class SQLiteAuditRepository(AuditRepository):
    def __init__(self, conn: Optional[sqlite3.Connection] = None) -> None:
        self._conn = conn

    def _get_conn(self) -> sqlite3.Connection:
        return self._conn if self._conn is not None else get_connection()

    def append(self, entry: AuditLogEntry) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO audit_log (workflow_id, data, timestamp) VALUES (?, ?, ?)",
            (entry.workflow_id, entry.model_dump_json(), entry.timestamp.isoformat()),
        )
        conn.commit()

    def list_for_workflow(self, workflow_id: str) -> List[AuditLogEntry]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT data FROM audit_log WHERE workflow_id = ? ORDER BY timestamp", (workflow_id,)
        ).fetchall()
        return [AuditLogEntry.model_validate_json(row["data"]) for row in rows]

    def count_all(self) -> int:
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()
        return int(row["n"])


class SQLiteNotificationRepository(NotificationRepository):
    def __init__(self, conn: Optional[sqlite3.Connection] = None) -> None:
        self._conn = conn

    def _get_conn(self) -> sqlite3.Connection:
        return self._conn if self._conn is not None else get_connection()

    def append(self, notification: Notification) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO notifications (notification_id, workflow_id, data, created_at) VALUES (?, ?, ?, ?)",
            (
                notification.notification_id,
                notification.workflow_id,
                notification.model_dump_json(),
                notification.created_at.isoformat(),
            ),
        )
        conn.commit()

    def list_for_workflow(self, workflow_id: str) -> List[Notification]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT data FROM notifications WHERE workflow_id = ? ORDER BY created_at", (workflow_id,)
        ).fetchall()
        return [Notification.model_validate_json(row["data"]) for row in rows]
