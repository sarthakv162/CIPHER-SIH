"""EventBus: fan-out, transform scoping, bounded mailboxes, and manager-event conversion."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from rupantar.api.events import EventBus, StreamEvent, Subscriber, model_payload
from rupantar.models._support import Event


def _drain(subscriber: Subscriber) -> list[StreamEvent]:
    out: list[StreamEvent] = []
    while not subscriber.queue.empty():
        out.append(subscriber.queue.get_nowait())
    return out


async def test_publish_fans_out_to_every_subscriber_of_that_transform() -> None:
    bus = EventBus()
    with bus.subscribe("t1") as a, bus.subscribe("t1") as b:
        bus.publish(StreamEvent("job", {"status": "RUNNING"}, "t1"))
        assert [e.data for e in _drain(a)] == [{"status": "RUNNING"}]
        assert [e.data for e in _drain(b)] == [{"status": "RUNNING"}]


async def test_transform_scoped_events_do_not_leak_across_transforms() -> None:
    bus = EventBus()
    with bus.subscribe("t1") as mine, bus.subscribe("t2") as other:
        bus.publish(StreamEvent("job", {"job_id": "j1"}, "t1"))
        assert len(_drain(mine)) == 1
        assert _drain(other) == []


async def test_global_events_reach_every_subscriber() -> None:
    bus = EventBus()
    with bus.subscribe("t1") as a, bus.subscribe("t2") as b:
        bus.publish(StreamEvent("model", {"kind": "LOAD_START"}))
        assert len(_drain(a)) == 1
        assert len(_drain(b)) == 1


async def test_subscribers_are_detached_when_the_connection_ends() -> None:
    bus = EventBus()
    with bus.subscribe("t1"):
        assert bus.subscriber_count == 1
    assert bus.subscriber_count == 0
    bus.publish(StreamEvent("job", {}, "t1"))


async def test_a_slow_subscriber_never_blocks_the_publisher() -> None:
    bus = EventBus(mailbox=4)
    with bus.subscribe("t1") as slow, bus.subscribe("t1") as fast:
        published = 0
        for index in range(200):
            await asyncio.wait_for(
                asyncio.to_thread(bus.publish, StreamEvent("token", {"i": index}, "t1")), 2.0
            )
            published += 1
            if index % 2 == 0:
                fast.queue.get_nowait()
        assert published == 200
        assert slow.queue.qsize() == 4
        assert slow.dropped == 196
        assert [e.data["i"] for e in _drain(slow)] == [196, 197, 198, 199]


async def test_full_mailbox_drops_oldest_not_newest() -> None:
    subscriber = Subscriber("t1", maxsize=2)
    for index in range(5):
        subscriber.offer(StreamEvent("token", {"i": index}, "t1"))
    assert [e.data["i"] for e in _drain(subscriber)] == [3, 4]


async def test_model_sink_lifts_rss_out_of_the_event_detail() -> None:
    bus = EventBus()
    event = Event(
        kind="EVICT_START",
        model_key="brain",
        pid=4242,
        ts=datetime(2026, 9, 9, tzinfo=UTC),
        detail={"reason": "make_room", "rss_mb": 3512.4},
    )
    with bus.subscribe("t1") as subscriber:
        await bus.model_sink(event)
        (frame,) = _drain(subscriber)
    assert frame.name == "model"
    assert frame.data["model_key"] == "brain"
    assert frame.data["pid"] == 4242
    assert frame.data["rss_mb"] == 3512.4
    assert frame.data["detail"] == {"reason": "make_room"}
    assert model_payload(event)["kind"] == "EVICT_START"


async def test_progress_sink_tags_orchestrator_events_with_their_transform() -> None:
    bus = EventBus()
    sink = bus.progress_sink("t9")
    with bus.subscribe("t9") as mine, bus.subscribe("other") as other:
        sink("job", {"job_id": "j1"})
        assert _drain(mine)[0].transform_id == "t9"
        assert _drain(other) == []


def test_running_registry_tracks_in_flight_transforms() -> None:
    bus = EventBus()
    assert not bus.is_running("t1")
    bus.mark_running("t1")
    assert bus.is_running("t1")
    bus.mark_finished("t1")
    assert not bus.is_running("t1")


@pytest.mark.parametrize("name", ["job", "model", "token", "verification", "transform"])
def test_sse_frame_is_well_formed(name: str) -> None:
    frame = StreamEvent(name, {"a": 1}).sse()
    assert frame.startswith(f"event: {name}\ndata: ")
    assert frame.endswith("\n\n")
    assert '"a": 1' in frame
