"""ModelManager: the single entry point that starts, leases, and evicts model processes."""

from __future__ import annotations

import asyncio
import contextlib
import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any

from rupantar.core.errors import AcquireTimeoutError, RuntimeStartError
from rupantar.models._ports import find_free_port
from rupantar.models._support import (
    EPOCH,
    Entry,
    Event,
    EventSink,
    Lease,
    ModelState,
    default_runtime_factory,
    store_event_sink,
    utcnow,
    wait_process_gone,
)
from rupantar.models.registry import ModelEntry, Registry
from rupantar.models.runtime_base import Runtime

_QUANT_RE = re.compile(r"I?Q\d[A-Za-z0-9_]*")


def _parse_quant(path: Path) -> str:
    """Best-effort GGUF quant tag parsed from a model filename, else 'unknown'."""
    match = _QUANT_RE.search(path.stem)
    return match.group(0) if match else "unknown"


__all__ = [
    "Event",
    "EventSink",
    "Lease",
    "ModelManager",
    "ModelState",
    "default_runtime_factory",
    "store_event_sink",
]


class ModelManager:
    """Owns every model child process. `acquire()` is the only way to start one."""

    def __init__(
        self,
        registry: Registry,
        *,
        policy: dict[str, Any] | None = None,
        runtime_factory: Callable[[ModelEntry, int], Runtime] | None = None,
        event_sink: EventSink | None = None,
        clock: Callable[[], datetime] = utcnow,
        reaper_interval: float = 30.0,
        idle_ttl: float | None = None,
        max_heavy_resident: int | None = None,
        acquire_timeout: float | None = None,
    ) -> None:
        """Wire the manager to a registry and policy without starting anything."""
        policy = policy or {}
        self._registry = registry
        self._factory = runtime_factory or default_runtime_factory(registry, policy)
        self._sink = event_sink
        self._clock = clock
        self._reaper_interval = reaper_interval
        self._idle_ttl = (
            float(policy.get("idle_ttl_seconds", 120)) if idle_ttl is None else idle_ttl
        )
        self._max_heavy = (
            int(policy.get("max_heavy_resident", 1))
            if max_heavy_resident is None
            else max_heavy_resident
        )
        self._acquire_timeout = (
            float(policy.get("acquire_timeout_seconds", 180))
            if acquire_timeout is None
            else acquire_timeout
        )
        low, high = policy.get("port_range", [8100, 8199])
        self._port_low, self._port_high = int(low), int(high)
        self._entries: dict[str, Entry] = {}
        self._cond = asyncio.Condition()
        self._reaper: asyncio.Task[None] | None = None
        self.events: list[Event] = []

    @asynccontextmanager
    async def acquire(self, key: str, *, timeout: float | None = None) -> AsyncIterator[Lease]:
        """Lease a resident model, loading and evicting as policy requires."""
        lease = await self.obtain(key, timeout=timeout)
        try:
            yield lease
        finally:
            await lease.release()

    async def obtain(self, key: str, *, timeout: float | None = None) -> Lease:
        """Acquire a lease without a context manager; the caller must release it."""
        budget = self._acquire_timeout if timeout is None else timeout
        try:
            return await asyncio.wait_for(self._obtain_inner(key), budget)
        except TimeoutError:
            raise AcquireTimeoutError(
                f"could not acquire model {key!r} within {budget:g}s; another heavy model holds "
                "the single residency slot — release its lease or raise "
                "policy.yaml:max_heavy_resident"
            ) from None

    async def release(self, lease: Lease) -> None:
        """Decrement a model's refcount and wake any waiters."""
        async with self._cond:
            entry = self._entries.get(lease.key)
            if entry is not None and entry.refcount > 0:
                entry.refcount -= 1
                entry.last_used = self._clock()
            self._cond.notify_all()

    async def evict(self, key: str) -> None:
        """Force-evict an idle model now; a no-op if it has active leases or is not READY."""
        async with self._cond:
            entry = self._entries.get(key)
            if entry is not None and entry.refcount == 0 and entry.state is ModelState.READY:
                await self._evict(entry, reason="manual")
            self._cond.notify_all()

    async def reap_idle(self) -> None:
        """Evict every heavy model idle longer than idle_ttl with refcount 0."""
        async with self._cond:
            now = self._clock()
            for entry in list(self._entries.values()):
                if (
                    entry.class_ == "heavy"
                    and entry.state is ModelState.READY
                    and entry.refcount == 0
                    and entry.last_used is not None
                    and (now - entry.last_used).total_seconds() > self._idle_ttl
                ):
                    await self._evict(entry, reason="idle_ttl")
            self._cond.notify_all()

    def model_meta(self, key: str) -> dict[str, Any]:
        """Provenance metadata for a model key: key, path, sha256, quant."""
        entry = self._registry.entry(key)
        if entry.is_stub:
            return {"key": key, "path": None, "sha256": None, "quant": "stub"}
        return {
            "key": key,
            "path": str(entry.path) if entry.path else None,
            "sha256": entry.sha256 or entry.declared_sha256,
            "quant": _parse_quant(entry.path) if entry.path else "unknown",
        }

    def status(self) -> list[dict[str, Any]]:
        """Snapshot of every registry model and its residency state."""
        rows: list[dict[str, Any]] = []
        for key in self._registry.key_list():
            entry = self._entries.get(key)
            runtime = entry.runtime if entry else None
            rss = runtime.rss_bytes() if runtime else None
            rows.append(
                {
                    "key": key,
                    "state": entry.state.name if entry else ModelState.NOT_LOADED.name,
                    "pid": runtime.pid if runtime else None,
                    "port": entry.port if entry else None,
                    "rss_mb": round(rss / 1_000_000, 1) if rss else None,
                    "refcount": entry.refcount if entry else 0,
                    "loaded_at": entry.loaded_at.isoformat() if entry and entry.loaded_at else None,
                    "last_used": entry.last_used.isoformat() if entry and entry.last_used else None,
                }
            )
        return rows

    def start_reaper(self) -> None:
        """Begin the idle-TTL eviction background task (idempotent)."""
        if self._reaper is None or self._reaper.done():
            self._reaper = asyncio.create_task(self._reap_loop())

    async def stop_reaper(self) -> None:
        """Stop the background reaper task."""
        if self._reaper is not None:
            self._reaper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reaper
            self._reaper = None

    async def start(self) -> None:
        """Optional lifecycle hook: start the background reaper. Prewarm is left to callers."""
        self.start_reaper()

    async def aclose(self) -> None:
        """Stop the reaper and terminate every resident model process."""
        await self.stop_reaper()
        async with self._cond:
            for entry in list(self._entries.values()):
                if entry.runtime is not None:
                    with contextlib.suppress(Exception):
                        await entry.runtime.stop()
                    entry.runtime = None
                    entry.port = None
                    entry.refcount = 0
                    entry.state = ModelState.NOT_LOADED
            self._cond.notify_all()

    async def __aenter__(self) -> ModelManager:
        """Enter the manager as an async context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Tear every model process down on context exit."""
        await self.aclose()

    async def _obtain_inner(self, key: str) -> Lease:
        """Core acquire loop, serialised through the manager condition."""
        entry = self._entry(key)
        async with self._cond:
            while True:
                if entry.state is ModelState.READY:
                    if entry.runtime is not None and entry.runtime.is_alive():
                        return self._lease(entry)
                    await self._discard(entry, reason="external_death")
                if entry.state in (ModelState.LOADING, ModelState.EVICTING):
                    await self._cond.wait()
                    continue
                if not await self._make_room_for(entry):
                    await self._cond.wait()
                    continue
                await self._load(entry)
                return self._lease(entry)

    def _lease(self, entry: Entry) -> Lease:
        """Register a new reference on a READY entry and return its lease."""
        assert entry.runtime is not None
        entry.refcount += 1
        entry.last_used = self._clock()
        self._cond.notify_all()
        return Lease(entry.key, entry.runtime.endpoint, entry.runtime.pid, self)

    async def _make_room_for(self, entry: Entry) -> bool:
        """Evict idle heavy models until `entry` fits; return False if it must wait."""
        if entry.class_ != "heavy":
            return True
        while True:
            others = self._heavy_occupants(exclude=entry)
            if len(others) < self._max_heavy:
                return True
            idle = sorted(
                (e for e in others if e.state is ModelState.READY and e.refcount == 0),
                key=lambda e: e.last_used or EPOCH,
            )
            if not idle:
                return False
            await self._evict(idle[0], reason="make_room")

    async def _load(self, entry: Entry) -> None:
        """Spawn `entry`'s runtime and mark it READY, or FAILED and raise on error."""
        port = find_free_port(self._port_low, self._port_high, exclude=self._ports_in_use())
        entry.port = port
        entry.state = ModelState.LOADING
        entry.runtime = self._factory(self._registry.entry(entry.key), port)
        await self._emit("LOAD_START", entry.key, None, port=port)
        self._cond.notify_all()
        try:
            await entry.runtime.start()
        except Exception as exc:
            runtime, entry.runtime = entry.runtime, None
            entry.state = ModelState.FAILED
            entry.port = None
            if runtime is not None:
                with contextlib.suppress(Exception):
                    await runtime.stop()
            self._cond.notify_all()
            raise RuntimeStartError(
                f"model {entry.key!r} failed to start on port {port}: {exc}"
            ) from exc
        entry.state = ModelState.READY
        entry.loaded_at = self._clock()
        entry.last_used = self._clock()
        await self._emit("LOAD_READY", entry.key, entry.runtime.pid, port=port)
        self._cond.notify_all()

    async def _evict(self, entry: Entry, *, reason: str) -> None:
        """Terminate a model's process, wait for the real OS exit, and clear its slot."""
        if entry.runtime is None:
            entry.state = ModelState.NOT_LOADED
            return
        runtime = entry.runtime
        pid = runtime.pid
        entry.state = ModelState.EVICTING
        await self._emit("EVICT_START", entry.key, pid, reason=reason)
        self._cond.notify_all()
        await runtime.stop()
        await wait_process_gone(pid)
        entry.runtime = None
        entry.port = None
        entry.refcount = 0
        entry.loaded_at = None
        entry.state = ModelState.NOT_LOADED
        await self._emit("EVICT_DONE", entry.key, pid, reason=reason)
        self._cond.notify_all()

    async def _discard(self, entry: Entry, *, reason: str) -> None:
        """Drop a dead runtime without counting it as a clean eviction."""
        runtime, entry.runtime = entry.runtime, None
        pid = runtime.pid if runtime else None
        await self._emit("PROCESS_DIED", entry.key, pid, reason=reason)
        entry.port = None
        entry.refcount = 0
        entry.loaded_at = None
        entry.state = ModelState.NOT_LOADED
        if runtime is not None:
            with contextlib.suppress(Exception):
                await runtime.stop()
        self._cond.notify_all()

    async def _reap_loop(self) -> None:
        """Evict idle heavy models on a fixed interval until cancelled."""
        while True:
            await asyncio.sleep(self._reaper_interval)
            with contextlib.suppress(Exception):
                await self.reap_idle()

    def _entry(self, key: str) -> Entry:
        """Return the tracked entry for `key`, creating a NOT_LOADED one on first use."""
        meta = self._registry.entry(key)
        if key not in self._entries:
            self._entries[key] = Entry(key=key, class_=meta.class_)
        return self._entries[key]

    def _heavy_occupants(self, *, exclude: Entry) -> list[Entry]:
        """Heavy entries currently holding or claiming the residency slot."""
        occupied = (ModelState.READY, ModelState.LOADING, ModelState.EVICTING)
        return [
            e
            for e in self._entries.values()
            if e is not exclude and e.class_ == "heavy" and e.state in occupied
        ]

    def _ports_in_use(self) -> set[int]:
        """Ports currently assigned to a runtime."""
        return {e.port for e in self._entries.values() if e.port is not None}

    async def _emit(self, kind: str, key: str, pid: int | None, **detail: Any) -> None:
        """Record an event locally and forward it to the sink when one is configured."""
        event = Event(kind=kind, model_key=key, pid=pid, ts=self._clock(), detail=detail)
        self.events.append(event)
        if self._sink is not None:
            await self._sink(event)
