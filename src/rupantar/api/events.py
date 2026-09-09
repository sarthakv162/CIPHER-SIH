"""In-process broadcast bus for the operator console's live stream.

The SQLite `events` table stays the audit trail; this bus is the live wire. Every subscriber
gets its own bounded mailbox and publishers never await one, so a stalled browser tab can
never slow the runner or the model manager down.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from rupantar.models._support import Event
from rupantar.orchestrator.progress import ProgressSink

DEFAULT_MAILBOX = 512


@dataclass(frozen=True)
class StreamEvent:
    """One frame on the wire. `transform_id=None` means broadcast to every subscriber."""

    name: str
    data: dict[str, Any] = field(default_factory=dict)
    transform_id: str | None = None

    def sse(self) -> str:
        """Serialise as a single Server-Sent Events frame."""
        payload = json.dumps(self.data, default=str)
        return f"event: {self.name}\ndata: {payload}\n\n"


class Subscriber:
    """One client's bounded mailbox; the oldest frame is dropped before a publisher blocks."""

    def __init__(self, transform_id: str, maxsize: int = DEFAULT_MAILBOX) -> None:
        """Create an empty mailbox scoped to one transform."""
        self.transform_id = transform_id
        self.queue: asyncio.Queue[StreamEvent] = asyncio.Queue(maxsize=maxsize)
        self.dropped = 0

    def wants(self, event: StreamEvent) -> bool:
        """True when this subscriber should see the event (global, or its own transform)."""
        return event.transform_id is None or event.transform_id == self.transform_id

    def offer(self, event: StreamEvent) -> None:
        """Enqueue without ever blocking, discarding the oldest frame when the mailbox is full."""
        while True:
            try:
                self.queue.put_nowait(event)
                return
            except asyncio.QueueFull:
                try:
                    self.queue.get_nowait()
                    self.dropped += 1
                except asyncio.QueueEmpty:
                    return


class EventBus:
    """Fan-out of job, token, model, and verification events to live SSE subscribers."""

    def __init__(self, *, mailbox: int = DEFAULT_MAILBOX) -> None:
        """Create an empty bus with no subscribers and no running transforms."""
        self._subscribers: set[Subscriber] = set()
        self._running: set[str] = set()
        self._mailbox = mailbox

    @property
    def subscriber_count(self) -> int:
        """How many SSE clients are currently attached."""
        return len(self._subscribers)

    def publish(self, event: StreamEvent) -> None:
        """Offer one event to every interested subscriber; never blocks, never raises."""
        for subscriber in list(self._subscribers):
            if subscriber.wants(event):
                subscriber.offer(event)

    @contextmanager
    def subscribe(self, transform_id: str) -> Iterator[Subscriber]:
        """Attach a mailbox for the duration of one SSE connection."""
        subscriber = Subscriber(transform_id, self._mailbox)
        self._subscribers.add(subscriber)
        try:
            yield subscriber
        finally:
            self._subscribers.discard(subscriber)

    async def model_sink(self, event: Event) -> None:
        """`ModelManager` EventSink adapter: broadcast one manager event to everybody."""
        self.publish(StreamEvent(name="model", data=model_payload(event)))

    def progress_sink(self, transform_id: str) -> ProgressSink:
        """A `ProgressSink` that tags every orchestrator event with its transform."""

        def emit(name: str, data: dict[str, Any]) -> None:
            self.publish(StreamEvent(name=name, data=data, transform_id=transform_id))

        return emit

    def mark_running(self, transform_id: str) -> None:
        """Record that a transform has a live background task in this process."""
        self._running.add(transform_id)

    def mark_finished(self, transform_id: str) -> None:
        """Record that a transform's background task has ended, however it ended."""
        self._running.discard(transform_id)

    def is_running(self, transform_id: str) -> bool:
        """True while a transform's background task is still in flight here."""
        return transform_id in self._running


def model_payload(event: Event) -> dict[str, Any]:
    """The wire shape of a model-manager event; `rss_mb` is lifted out of the detail."""
    detail = dict(event.detail)
    return {
        "kind": event.kind,
        "model_key": event.model_key,
        "pid": event.pid,
        "rss_mb": detail.pop("rss_mb", None),
        "ts": event.ts.isoformat(),
        "detail": detail,
    }
