"""Strict tool-calling contract.

Every tool is a registered function with a Pydantic input schema and a
Pydantic output schema. Agents never execute arbitrary code and never call
a function directly -- they only ever go through
``invoke_tool(name, payload, workflow_id)``, which:

  1. looks the tool up in an explicit allowlist (KeyError if not found --
     there is no dynamic dispatch by attacker-controlled string beyond
     this fixed dict),
  2. validates the input payload against the tool's Pydantic input model
     (rejects malformed payloads before they ever reach the tool body),
  3. applies the per-workflow rate limiter,
  4. calls the tool,
  5. validates the return value against the tool's Pydantic output model
     (a tool that returns something malformed is a bug, and this catches
     it immediately rather than letting bad data flow downstream).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Type

from pydantic import BaseModel, ValidationError

from backend.tools.rate_limiter import ToolRateLimitError, get_rate_limiter

logger = logging.getLogger("govflow.tools.registry")


class ToolValidationError(Exception):
    """Raised when a tool's input or output fails schema validation."""


class ToolNotFoundError(Exception):
    """Raised when invoke_tool is called with an unregistered tool name."""


@dataclass
class ToolSpec:
    name: str
    func: Callable[[BaseModel], BaseModel]
    input_model: Type[BaseModel]
    output_model: Type[BaseModel]
    description: str = ""
    rate_limited: bool = True


_registry: Dict[str, ToolSpec] = {}


def register_tool(
    name: str,
    input_model: Type[BaseModel],
    output_model: Type[BaseModel],
    description: str = "",
    rate_limited: bool = True,
):
    """Decorator that registers a plain function (payload_model) -> output_model
    into the tool allowlist under ``name``.

    ``rate_limited=False`` is for internal bookkeeping tools (audit
    logging, workflow-state patches, RAG lookups) that aren't external
    calls and shouldn't share a budget meant to cap calls to the mock
    government API tools -- AuditAgent's bus-wide safety net alone doubles
    append_audit_entry call volume, so exempting it (and the other
    internal tools) keeps the rate limit meaningful without risking a
    false-positive failure mid-demo.
    """

    def decorator(func: Callable[[BaseModel], BaseModel]) -> Callable[[BaseModel], BaseModel]:
        if name in _registry:
            raise ValueError(f"tool {name!r} is already registered")
        _registry[name] = ToolSpec(
            name=name,
            func=func,
            input_model=input_model,
            output_model=output_model,
            description=description,
            rate_limited=rate_limited,
        )
        logger.debug("registered tool %s", name)
        return func

    return decorator


def list_tools() -> Dict[str, ToolSpec]:
    return dict(_registry)


def clear_tools() -> None:
    """Test helper."""
    _registry.clear()


def invoke_tool(name: str, payload: Dict[str, Any], workflow_id: str) -> BaseModel:
    spec = _registry.get(name)
    if spec is None:
        raise ToolNotFoundError(f"tool {name!r} is not registered. Allowed tools: {sorted(_registry)}")

    if spec.rate_limited:
        try:
            get_rate_limiter().check(workflow_id)
        except ToolRateLimitError:
            logger.warning("rate limit exceeded: workflow=%s tool=%s", workflow_id, name)
            raise

    try:
        validated_input = spec.input_model.model_validate(payload)
    except ValidationError as exc:
        raise ToolValidationError(f"invalid input for tool {name!r}: {exc}") from exc

    result = spec.func(validated_input)

    if not isinstance(result, spec.output_model):
        try:
            result = spec.output_model.model_validate(result)
        except ValidationError as exc:
            raise ToolValidationError(f"invalid output from tool {name!r}: {exc}") from exc

    logger.info("tool invoked: workflow=%s tool=%s", workflow_id, name)
    return result
