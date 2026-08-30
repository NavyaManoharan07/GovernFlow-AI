import pytest

from backend.events.bus import InProcessEventBus
from backend.events.retry import with_retry
from backend.models.enums import EventType
from backend.models.event import Event


@pytest.mark.asyncio
async def test_publish_fires_registered_handler():
    bus = InProcessEventBus()
    received = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(EventType.WORKFLOW_CREATED, handler)

    event = Event(workflow_id="wf-1", event_type=EventType.WORKFLOW_CREATED, payload={"goal": "test"})
    await bus.publish(event)

    assert len(received) == 1
    assert received[0].event_id == event.event_id


@pytest.mark.asyncio
async def test_publish_fires_wildcard_handler():
    bus = InProcessEventBus()
    received = []

    async def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe_all(handler)

    event = Event(workflow_id="wf-1", event_type=EventType.GOAL_ANALYZED)
    await bus.publish(event)

    assert len(received) == 1


@pytest.mark.asyncio
async def test_publish_does_not_crash_when_handler_raises():
    bus = InProcessEventBus()

    async def bad_handler(event: Event) -> None:
        raise RuntimeError("boom")

    bus.subscribe(EventType.WORKFLOW_CREATED, bad_handler)

    event = Event(workflow_id="wf-1", event_type=EventType.WORKFLOW_CREATED)
    # Should not raise -- InProcessEventBus isolates handler failures.
    await bus.publish(event)


@pytest.mark.asyncio
async def test_retry_eventually_succeeds():
    attempts = []

    async def flaky_handler(event: Event) -> None:
        attempts.append(1)
        if len(attempts) < 2:
            raise RuntimeError("transient")

    wrapped = with_retry(flaky_handler, max_attempts=3, base_delay_seconds=0.01)
    event = Event(workflow_id="wf-1", event_type=EventType.WORKFLOW_CREATED)
    await wrapped(event)

    assert len(attempts) == 2


@pytest.mark.asyncio
async def test_retry_gives_up_after_max_attempts_and_publishes_failure_event():
    attempts = []
    published = []

    async def always_fails(event: Event) -> None:
        attempts.append(1)
        raise RuntimeError("permanent failure")

    async def capture_publish(event: Event) -> None:
        published.append(event)

    wrapped = with_retry(
        always_fails,
        max_attempts=3,
        base_delay_seconds=0.01,
        publish_failure_event=capture_publish,
    )
    event = Event(workflow_id="wf-1", event_type=EventType.WORKFLOW_CREATED)
    await wrapped(event)

    assert len(attempts) == 3
    assert len(published) == 1
    assert published[0].event_type == EventType.WORKFLOW_FAILED
    assert published[0].workflow_id == "wf-1"


@pytest.mark.asyncio
async def test_bus_wired_with_retry_on_persistent_failure_publishes_workflow_failed():
    bus = InProcessEventBus()
    seen_failures = []

    async def always_fails(event: Event) -> None:
        raise RuntimeError("nope")

    async def on_failure(event: Event) -> None:
        seen_failures.append(event)

    bus.subscribe(
        EventType.WORKFLOW_CREATED,
        with_retry(always_fails, max_attempts=2, base_delay_seconds=0.01, publish_failure_event=bus.publish),
    )
    bus.subscribe(EventType.WORKFLOW_FAILED, on_failure)

    await bus.publish(Event(workflow_id="wf-2", event_type=EventType.WORKFLOW_CREATED))

    assert len(seen_failures) == 1
    assert seen_failures[0].workflow_id == "wf-2"
