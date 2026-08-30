"""Tool registry package.

Importing this package registers every tool (decorators run at import
time). backend/agents/wiring.py imports backend.tools to guarantee the
allowlist is populated before any agent runs.
"""

from backend.tools.context import ToolContext, get_tool_context, set_tool_context, reset_tool_context
from backend.tools.rate_limiter import ToolRateLimitError, get_rate_limiter, reset_rate_limiter
from backend.tools.registry import (
    ToolNotFoundError,
    ToolValidationError,
    invoke_tool,
    list_tools,
    clear_tools,
)
from backend.tools.security import wrap_untrusted, looks_like_injection_attempt

# Import for side effects: each module registers its tools via the
# @register_tool decorator.
from backend.tools import government_tools  # noqa: F401
from backend.tools import workflow_tools  # noqa: F401
from backend.tools import rag_tools  # noqa: F401

__all__ = [
    "ToolContext",
    "get_tool_context",
    "set_tool_context",
    "reset_tool_context",
    "ToolRateLimitError",
    "get_rate_limiter",
    "reset_rate_limiter",
    "ToolNotFoundError",
    "ToolValidationError",
    "invoke_tool",
    "list_tools",
    "clear_tools",
    "wrap_untrusted",
    "looks_like_injection_attempt",
]
