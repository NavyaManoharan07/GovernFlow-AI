"""Simple in-memory per-workflow rate limiter for tool calls.

A fixed-window counter is sufficient for a hackathon demo (single process,
short-lived workflows) -- no need for a sliding window or a shared store.
Configured via MAX_TOOL_CALLS_PER_MINUTE.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Dict, List


class ToolRateLimitError(Exception):
    def __init__(self, workflow_id: str, limit: int, window_seconds: float) -> None:
        self.workflow_id = workflow_id
        self.limit = limit
        super().__init__(
            f"workflow {workflow_id!r} exceeded the tool-call rate limit "
            f"({limit} calls per {window_seconds:.0f}s)"
        )


class ToolRateLimiter:
    def __init__(self, max_calls_per_minute: int, window_seconds: float = 60.0) -> None:
        self.max_calls_per_minute = max_calls_per_minute
        self.window_seconds = window_seconds
        self._calls: Dict[str, List[float]] = defaultdict(list)

    def check(self, workflow_id: str) -> None:
        """Raises ToolRateLimitError if this call would exceed the limit;
        otherwise records the call."""
        now = time.monotonic()
        window_start = now - self.window_seconds
        recent = [t for t in self._calls[workflow_id] if t >= window_start]
        if len(recent) >= self.max_calls_per_minute:
            self._calls[workflow_id] = recent
            raise ToolRateLimitError(workflow_id, self.max_calls_per_minute, self.window_seconds)
        recent.append(now)
        self._calls[workflow_id] = recent

    def reset(self) -> None:
        self._calls.clear()


_singleton_limiter: ToolRateLimiter | None = None


def get_rate_limiter() -> ToolRateLimiter:
    global _singleton_limiter
    if _singleton_limiter is None:
        max_calls = int(os.environ.get("MAX_TOOL_CALLS_PER_MINUTE", "30"))
        _singleton_limiter = ToolRateLimiter(max_calls)
    return _singleton_limiter


def reset_rate_limiter() -> None:
    """Test helper."""
    global _singleton_limiter
    _singleton_limiter = None
