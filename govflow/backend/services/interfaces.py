"""Repository interfaces (protocols) for persistence.

Concrete implementations: SQLite (local, fully working) and Firestore
(cloud, stubbed in Part 1). Callers should depend on these abstract
interfaces, not the concrete classes, so swapping PERSISTENCE_MODE never
requires touching call sites.
"""

from __future__ import annotations

import abc
from typing import List, Optional

from backend.models.audit import AuditLogEntry
from backend.models.event import Event
from backend.models.notification import Notification
from backend.models.workflow import Workflow


class WorkflowRepository(abc.ABC):
    @abc.abstractmethod
    def create(self, workflow: Workflow) -> None: ...

    @abc.abstractmethod
    def get(self, workflow_id: str) -> Optional[Workflow]: ...

    @abc.abstractmethod
    def update(self, workflow: Workflow) -> None: ...

    @abc.abstractmethod
    def list(self, user_id: Optional[str] = None) -> List[Workflow]: ...


class EventRepository(abc.ABC):
    @abc.abstractmethod
    def append(self, event: Event) -> None: ...

    @abc.abstractmethod
    def list_for_workflow(self, workflow_id: str) -> List[Event]: ...


class AuditRepository(abc.ABC):
    @abc.abstractmethod
    def append(self, entry: AuditLogEntry) -> None: ...

    @abc.abstractmethod
    def list_for_workflow(self, workflow_id: str) -> List[AuditLogEntry]: ...


class NotificationRepository(abc.ABC):
    """Added in Part 2 so NotificationAgent has somewhere real to persist to."""

    @abc.abstractmethod
    def append(self, notification: Notification) -> None: ...

    @abc.abstractmethod
    def list_for_workflow(self, workflow_id: str) -> List[Notification]: ...
