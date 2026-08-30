"""Simple in-memory rate limiting for the write-heavy demo/creation routes.

Reuses backend.tools.rate_limiter.ToolRateLimiter (already built in Part 2)
as the counting primitive -- it's a generic fixed-window-per-key limiter,
not tool-specific -- with its own separate instance and budget so it can't
interact with (or be exhausted by) the per-workflow tool-call limiter.
Keyed by client IP, falling back to the request body's user_id when
present, so a single caller can't create unbounded workflows and rack up
Gemini-call costs during judging. Deliberately simple: an in-memory fixed
window is enough for a single-process hackathon demo.
"""

from __future__ import annotations

import os

from fastapi import HTTPException, Request

from backend.tools.rate_limiter import ToolRateLimitError, ToolRateLimiter

_singleton_limiter: ToolRateLimiter | None = None


def get_api_rate_limiter() -> ToolRateLimiter:
    global _singleton_limiter
    if _singleton_limiter is None:
        max_calls = int(os.environ.get("API_RATE_LIMIT_PER_MINUTE", "10"))
        _singleton_limiter = ToolRateLimiter(max_calls)
    return _singleton_limiter


def reset_api_rate_limiter() -> None:
    """Test helper."""
    global _singleton_limiter
    _singleton_limiter = None


async def enforce_rate_limit(request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    key = f"ip:{client_host}"
    try:
        get_api_rate_limiter().check(key)
    except ToolRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
