"""Support types for ModelManager: state enum, events, leases, and the default factory."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from rupantar.core.store import Store
from rupantar.models.registry import ModelEntry, Registry
from rupantar.models.runtime_base import Runtime
from rupantar.models.runtime_stub import StubRuntime

if TYPE_CHECKING:
    from rupantar.models.manager import ModelManager

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class ModelState(Enum):
    """Lifecycle of one managed model."""

    NOT_LOADED = auto()
    LOADING = auto()
    READY = auto()
    EVICTING = auto()
    FAILED = auto()


@dataclass(frozen=True)
class Event:
    """A structured manager event, for observers and the invariant tests."""

    kind: str
    model_key: str
    pid: int | None
    ts: datetime
    detail: dict[str, Any] = field(default_factory=dict)


EventSink = Callable[[Event], Awaitable[None]]


@dataclass
class Entry:
    """Mutable per-model bookkeeping."""

    key: str
    class_: str
    state: ModelState = ModelState.NOT_LOADED
    runtime: Runtime | None = None
    port: int | None = None
    refcount: int = 0
    loaded_at: datetime | None = None
    last_used: datetime | None = None


@dataclass
class Lease:
    """A reference-counted handle to a resident model."""

    key: str
    endpoint: str
    pid: int | None
    _manager: ModelManager
    _released: bool = False

    async def release(self) -> None:
        """Decrement the model refcount exactly once."""
        if not self._released:
            self._released = True
            await self._manager.release(self)


def utcnow() -> datetime:
    """Timezone-aware present instant."""
    return datetime.now(UTC)


async def wait_process_gone(
    pid: int | None, *, timeout: float = 10.0, interval: float = 0.05
) -> None:
    """Poll os.kill(pid, 0) until the OS process is unreachable or `timeout` elapses."""
    if pid is None:
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            return
        await asyncio.sleep(interval)


def store_event_sink(store: Store) -> EventSink:
    """An event sink that appends every manager event to the store's events table."""

    async def _sink(event: Event) -> None:
        await store.append_event(
            kind=event.kind,
            model_key=event.model_key,
            pid=event.pid,
            ts=event.ts.isoformat(),
            detail=event.detail,
        )

    return _sink


def default_runtime_factory(
    registry: Registry, policy: dict[str, Any]
) -> Callable[[ModelEntry, int], Runtime]:
    """Build a factory mapping a ModelEntry plus a port to a concrete Runtime."""
    poll = float(policy.get("health_poll_interval", 0.5))

    def _make(entry: ModelEntry, port: int) -> Runtime:
        if entry.is_stub:
            return StubRuntime(
                key=entry.key,
                class_=entry.class_,
                port=port,
                health_timeout=poll * 40 + 5,
                health_interval=poll,
            )
        if entry.runtime == "whisper":
            from rupantar.models.runtime_whisper import WhisperRuntime

            return WhisperRuntime(
                entry=entry,
                port=port,
                health_timeout=float(policy.get("health_timeout_seconds", 120)),
                health_interval=poll,
            )
        from rupantar.models.runtime_llama import LlamaRuntime

        llama = registry.runtime_spec("llama")
        return LlamaRuntime(
            entry=entry,
            port=port,
            binary=str(llama.get("binary", "llama-server")),
            host=str(llama.get("host", "127.0.0.1")),
            common_args=[str(a) for a in llama.get("common_args", [])],
            health_timeout=float(policy.get("health_timeout_seconds", 120)),
            health_interval=poll,
        )

    return _make
