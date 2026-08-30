"""Retry wrapper for event handlers.

Wraps an async handler so transient failures are retried with exponential
backoff (max 3 attempts). On final failure, instead of letting the
exception crash the process, it publishes a failure event (WORKFLOW_FAILED
by default, or a caller-supplied step-level failure event) so the system
degrades gracefully and observably.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional

from backend.models.enums import EventType
from backend.models.event import Event

logger = logging.getLogger("govflow.events.retry")

HandlerFunc = Callable[[Event], Awaitable[None]]
FailureEventBuilder = Callable[[Event, Exception], Event]


def _default_failure_event(event: Event, error: Exception) -> Event:
    return Event(
        workflow_id=event.workflow_id,
        event_type=EventType.WORKFLOW_FAILED,
        payload={
            "reason": f"handler failed after retries: {error}",
            "failed_event_type": event.event_type.value,
            "original_payload": event.payload,
        },
        source_agent="retry_wrapper",
        correlation_id=event.correlation_id,
    )


def with_retry(
    handler: HandlerFunc,
    *,
    max_attempts: int = 3,
    base_delay_seconds: float = 0.1,
    publish_failure_event: Optional[Callable[[Event], Awaitable[None]]] = None,
    failure_event_builder: FailureEventBuilder = _default_failure_event,
) -> HandlerFunc:
    """Return a wrapped handler with retry + exponential backoff.

    Args:
        handler: the async handler to protect.
        max_attempts: maximum number of attempts (default 3).
        base_delay_seconds: base delay for exponential backoff (delay = base * 2**attempt).
        publish_failure_event: async callable(event) invoked on final failure,
            typically an EventBus.publish bound method. If None, the failure
            is only logged (used mainly for tests).
        failure_event_builder: builds the Event to publish on final failure.
    """

    async def wrapped(event: Event) -> None:
        attempt = 0
        last_error: Optional[Exception] = None
        while attempt < max_attempts:
            try:
                await handler(event)
                return
            except Exception as exc:  # noqa: BLE001 - intentionally broad, retried
                last_error = exc
                attempt += 1
                logger.warning(
                    "handler %s failed on attempt %d/%d for event_type=%s: %s",
                    getattr(handler, "__name__", repr(handler)),
                    attempt,
                    max_attempts,
                    event.event_type,
                    exc,
                )
                if attempt < max_attempts:
                    delay = base_delay_seconds * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)

        logger.error(
            "handler %s exhausted %d attempts for event_type=%s workflow_id=%s, giving up: %s",
            getattr(handler, "__name__", repr(handler)),
            max_attempts,
            event.event_type,
            event.workflow_id,
            last_error,
        )
        if publish_failure_event is not None and last_error is not None:
            failure_event = failure_event_builder(event, last_error)
            await publish_failure_event(failure_event)

    wrapped.__name__ = f"with_retry({getattr(handler, '__name__', 'handler')})"
    return wrapped
