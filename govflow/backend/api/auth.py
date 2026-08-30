"""Lightweight API-key auth placeholder for write routes.

Defaults to DISABLED (API_KEY_REQUIRED unset/false) so local dev and the
demo are never blocked. Flip API_KEY_REQUIRED=true and set API_KEY in the
environment to require an X-API-Key header matching it on write routes --
a config flip, not a rewrite, since every write route already depends on
`require_api_key`.
"""

from __future__ import annotations

import os

from fastapi import Header, HTTPException


def _auth_enabled() -> bool:
    return os.environ.get("API_KEY_REQUIRED", "false").strip().lower() in {"1", "true", "yes"}


async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not _auth_enabled():
        return

    expected = os.environ.get("API_KEY", "")
    if not expected:
        # Misconfiguration: auth required but no key configured to check
        # against. Fail closed (never silently allow) but say so clearly
        # server-side rather than a generic 401.
        raise HTTPException(status_code=500, detail="API_KEY_REQUIRED is set but API_KEY is not configured")

    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Key header")
