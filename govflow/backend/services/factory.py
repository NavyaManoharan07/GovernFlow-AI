"""Factory for repository implementations, gated by PERSISTENCE_MODE=local|firestore."""

from __future__ import annotations

import os
from typing import Tuple

from backend.services.interfaces import (
    AuditRepository,
    EventRepository,
    NotificationRepository,
    WorkflowRepository,
)


def get_repositories() -> Tuple[WorkflowRepository, EventRepository, AuditRepository, NotificationRepository]:
    """Returns (workflow_repo, event_repo, audit_repo, notification_repo).

    Part 2 note: notification_repo was added alongside NotificationAgent.
    This changes the factory's return arity from a 3-tuple to a 4-tuple --
    the only call site (backend/main.py) was updated accordingly.
    """
    mode = os.environ.get("PERSISTENCE_MODE", "local").strip().lower()
    if mode == "local":
        from backend.services.sqlite_repo import (
            SQLiteAuditRepository,
            SQLiteEventRepository,
            SQLiteNotificationRepository,
            SQLiteWorkflowRepository,
        )

        return (
            SQLiteWorkflowRepository(),
            SQLiteEventRepository(),
            SQLiteAuditRepository(),
            SQLiteNotificationRepository(),
        )
    if mode == "firestore":
        from backend.services.firestore_repo import (
            FirestoreAuditRepository,
            FirestoreEventRepository,
            FirestoreNotificationRepository,
            FirestoreWorkflowRepository,
        )

        return (
            FirestoreWorkflowRepository(),
            FirestoreEventRepository(),
            FirestoreAuditRepository(),
            FirestoreNotificationRepository(),
        )
    raise ValueError(f"Unknown PERSISTENCE_MODE={mode!r}. Expected 'local' or 'firestore'.")
