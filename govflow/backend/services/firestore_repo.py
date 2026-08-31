"""Firestore-backed repository stubs.

Not implemented in Part 1. These exist so the interface seam is visible
and PERSISTENCE_MODE=firestore fails loudly (not silently) until a real
implementation lands.
"""

from __future__ import annotations

from typing import List, Optional

from backend.models.audit import AuditLogEntry
from backend.models.event import Event
from backend.models.notification import Notification
from backend.models.workflow import Workflow
from backend.services.interfaces import (
    AuditRepository,
    EventRepository,
    NotificationRepository,
    WorkflowRepository,
)

_NOT_IMPLEMENTED_MSG = (
    "{cls} is not implemented yet. To use Firestore, set GOOGLE_CLOUD_PROJECT, "
    "FIRESTORE_DATABASE, and GOOGLE_APPLICATION_CREDENTIALS, install "
    "google-cloud-firestore, and implement backend.services.firestore_repo.{cls} "
    "(planned for a later part). For local development, set PERSISTENCE_MODE=local instead."
)


class FirestoreWorkflowRepository(WorkflowRepository):
    def __init__(self) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(cls=type(self).__name__))

    def create(self, workflow: Workflow) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(cls=type(self).__name__))

    def get(self, workflow_id: str) -> Optional[Workflow]:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(cls=type(self).__name__))

    def update(self, workflow: Workflow) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(cls=type(self).__name__))

    def list(self, user_id: Optional[str] = None) -> List[Workflow]:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(cls=type(self).__name__))


class FirestoreEventRepository(EventRepository):
    def __init__(self) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(cls=type(self).__name__))

    def append(self, event: Event) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(cls=type(self).__name__))

    def list_for_workflow(self, workflow_id: str) -> List[Event]:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(cls=type(self).__name__))


class FirestoreAuditRepository(AuditRepository):
    def __init__(self) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(cls=type(self).__name__))

    def append(self, entry: AuditLogEntry) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(cls=type(self).__name__))

    def list_for_workflow(self, workflow_id: str) -> List[AuditLogEntry]:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(cls=type(self).__name__))

    def count_all(self) -> int:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(cls=type(self).__name__))


class FirestoreNotificationRepository(NotificationRepository):
    def __init__(self) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(cls=type(self).__name__))

    def append(self, notification: Notification) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(cls=type(self).__name__))

    def list_for_workflow(self, workflow_id: str) -> List[Notification]:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG.format(cls=type(self).__name__))
