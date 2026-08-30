"""In-memory AgentInfo registry that reflects real agent activity.

Replaces Part 1's static PLANNED_AGENTS list-as-data: this module seeds
itself from PLANNED_AGENTS at import time, then every Agent (base.py)
updates its own entry in place as it actually runs. Part 3 exposes this
via a GET route; for Part 2 it's readable in-process and covered by tests.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.models.agent import PLANNED_AGENTS, AgentInfo

_lock = threading.Lock()
_agents: Dict[str, AgentInfo] = {info.name: info.model_copy() for info in PLANNED_AGENTS}


def get_all() -> List[AgentInfo]:
    with _lock:
        return [info.model_copy() for info in _agents.values()]


def get(name: str) -> Optional[AgentInfo]:
    with _lock:
        info = _agents.get(name)
        return info.model_copy() if info else None


def update_status(name: str, status: str, last_action: Optional[str] = None) -> None:
    with _lock:
        info = _agents.get(name)
        if info is None:
            info = AgentInfo(name=name, responsibility="")
        info.status = status
        if last_action is not None:
            info.last_action = last_action
        info.last_active_at = datetime.now(timezone.utc)
        _agents[name] = info


def reset() -> None:
    """Test helper: restores the registry to its seeded (idle) state."""
    global _agents
    with _lock:
        _agents = {info.name: info.model_copy() for info in PLANNED_AGENTS}
