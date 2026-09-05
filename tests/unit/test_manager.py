"""ModelManager: leasing, single heavy residency, concurrency, reaper, death recovery."""

from __future__ import annotations

import asyncio
import os
import signal
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from rupantar.core.config import Env, load_config
from rupantar.core.errors import AcquireTimeoutError, UnknownModelError
from rupantar.models.manager import Event, Lease, ModelManager
from rupantar.models.registry import Registry
from rupantar.models.runtime_base import http_get_status

_CONFIGS = Path(__file__).resolve().parents[2] / "configs"
_POLICY = {"port_range": [8100, 8199], "max_heavy_resident": 1}


class FakeClock:
    """A monotonic clock the test drives by hand."""

    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def _registry() -> Registry:
    config = load_config(_CONFIGS, env=Env(profile="test-stub", db=None))
    return Registry.from_config(config, verify=False)


def _row(manager: ModelManager, key: str) -> dict[str, object]:
    return next(r for r in manager.status() if r["key"] == key)


async def _alive(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.fixture
async def manager() -> AsyncIterator[ModelManager]:
    mgr = ModelManager(_registry(), policy=_POLICY)
    try:
        yield mgr
    finally:
        await mgr.aclose()


async def test_acquire_yields_lease_and_refcounts(manager: ModelManager) -> None:
    async with manager.acquire("brain") as lease:
        assert isinstance(lease, Lease)
        assert lease.key == "brain"
        assert lease.endpoint.startswith("http://127.0.0.1:")
        assert await _alive(lease.pid)
        assert _row(manager, "brain")["state"] == "READY"
        assert _row(manager, "brain")["refcount"] == 1
    assert _row(manager, "brain")["refcount"] == 0
    assert _row(manager, "brain")["state"] == "READY"


async def test_unknown_key_raises(manager: ModelManager) -> None:
    with pytest.raises(UnknownModelError):
        await manager.obtain("ghost")


async def test_repeated_acquire_reuses_one_process(manager: ModelManager) -> None:
    async with manager.acquire("brain") as first, manager.acquire("brain") as second:
        assert first.pid == second.pid
    starts = [e for e in manager.events if e.kind == "LOAD_START" and e.model_key == "brain"]
    assert len(starts) == 1


async def test_concurrent_acquire_starts_exactly_one_process(manager: ModelManager) -> None:
    release_gate = asyncio.Event()
    pids: list[int | None] = []

    async def hold() -> None:
        async with manager.acquire("brain") as lease:
            pids.append(lease.pid)
            await release_gate.wait()

    tasks = [asyncio.create_task(hold()) for _ in range(3)]
    while len(pids) < 3:
        await asyncio.sleep(0.01)
    release_gate.set()
    await asyncio.gather(*tasks)

    assert len(set(pids)) == 1
    assert len([e for e in manager.events if e.kind == "LOAD_START"]) == 1


async def test_heavy_eviction_waits_for_exit_then_loads(manager: ModelManager) -> None:
    async with manager.acquire("brain") as lease:
        brain_pid = lease.pid
    async with manager.acquire("vlm") as lease:
        vlm_pid = lease.pid
        assert brain_pid != vlm_pid
        assert not await _alive(brain_pid)
        assert await _alive(vlm_pid)

    assert [(e.kind, e.model_key) for e in manager.events] == [
        ("LOAD_START", "brain"),
        ("LOAD_READY", "brain"),
        ("EVICT_START", "brain"),
        ("EVICT_DONE", "brain"),
        ("LOAD_START", "vlm"),
        ("LOAD_READY", "vlm"),
    ]


async def test_busy_heavy_blocks_until_timeout(manager: ModelManager) -> None:
    async with manager.acquire("brain"):
        with pytest.raises(AcquireTimeoutError):
            await manager.obtain("vlm", timeout=0.3)


async def test_light_model_does_not_evict_heavy(manager: ModelManager) -> None:
    async with manager.acquire("brain") as brain, manager.acquire("asr") as asr:
        assert await _alive(brain.pid)
        assert await _alive(asr.pid)
    assert not any(e.kind == "EVICT_START" for e in manager.events)


async def test_external_death_is_detected_and_recovered(manager: ModelManager) -> None:
    async with manager.acquire("brain") as lease:
        first_pid = lease.pid
    assert first_pid is not None

    os.kill(first_pid, signal.SIGKILL)
    await asyncio.sleep(0.1)

    async with manager.acquire("brain") as lease:
        assert lease.pid != first_pid
        assert await _alive(lease.pid)
        url = lease.endpoint + "/health"
        assert await asyncio.to_thread(lambda: http_get_status(url) == 200)
    assert any(e.kind == "PROCESS_DIED" for e in manager.events)


async def test_event_sink_receives_the_stream() -> None:
    captured: list[Event] = []

    async def sink(event: Event) -> None:
        captured.append(event)

    mgr = ModelManager(_registry(), policy=_POLICY, event_sink=sink)
    try:
        async with mgr.acquire("brain"):
            pass
    finally:
        await mgr.aclose()
    assert [e.kind for e in captured] == [e.kind for e in mgr.events]
    assert {"LOAD_START", "LOAD_READY"} <= {e.kind for e in captured}


async def test_manual_evict_kills_process(manager: ModelManager) -> None:
    lease = await manager.obtain("brain")
    pid = lease.pid
    await lease.release()
    await manager.evict("brain")
    assert not await _alive(pid)
    assert _row(manager, "brain")["state"] == "NOT_LOADED"


async def test_reaper_task_starts_and_stops(manager: ModelManager) -> None:
    manager.start_reaper()
    manager.start_reaper()
    await manager.stop_reaper()
    await manager.stop_reaper()


async def test_idle_ttl_reaper_evicts_idle_heavy() -> None:
    clock = FakeClock()
    mgr = ModelManager(_registry(), policy={"port_range": [8100, 8199]}, clock=clock, idle_ttl=1.0)
    try:
        lease = await mgr.obtain("brain")
        pid = lease.pid
        await lease.release()
        clock.advance(999)
        await mgr.reap_idle()
        assert not await _alive(pid)
        assert _row(mgr, "brain")["state"] == "NOT_LOADED"
        assert any(e.kind == "EVICT_DONE" and e.model_key == "brain" for e in mgr.events)
    finally:
        await mgr.aclose()


async def test_idle_reaper_keeps_leased_model() -> None:
    clock = FakeClock()
    mgr = ModelManager(_registry(), policy={"port_range": [8100, 8199]}, clock=clock, idle_ttl=1.0)
    try:
        async with mgr.acquire("brain"):
            clock.advance(999)
            await mgr.reap_idle()
            assert _row(mgr, "brain")["state"] == "READY"
    finally:
        await mgr.aclose()
