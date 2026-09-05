"""INV-2: never two heavy models resident at once.

Proven two ways: (1) reconstruct the READY set over time from the LOAD_START / LOAD_READY /
EVICT_START / EVICT_DONE stream and assert no two heavy models are ever simultaneously READY;
(2) live os.kill(pid, 0) probes showing the old process is dead before the new one is alive.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterable
from pathlib import Path

import pytest

from rupantar.core.config import Env, load_config
from rupantar.models.manager import Event, ModelManager
from rupantar.models.registry import Registry

_CONFIGS = Path(__file__).resolve().parents[2] / "configs"
_HEAVY = {"brain", "vlm"}


def _manager() -> ModelManager:
    config = load_config(_CONFIGS, env=Env(profile="test-stub", db=None))
    return ModelManager(
        Registry.from_config(config, verify=False),
        policy={"port_range": [8100, 8199], "max_heavy_resident": 1},
    )


@pytest.fixture
async def manager() -> AsyncIterator[ModelManager]:
    mgr = _manager()
    try:
        yield mgr
    finally:
        await mgr.aclose()


def _pid_alive(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _assert_never_two_heavy_ready(events: Iterable[Event]) -> None:
    """Replay the event stream; a heavy model is READY between LOAD_READY and EVICT_START."""
    ready: set[str] = set()
    claimed: set[str] = set()
    for event in events:
        if event.kind == "LOAD_START":
            live_heavy = (claimed & _HEAVY) - {event.model_key}
            assert not live_heavy, f"{event.model_key} load began while heavy {live_heavy} resident"
            claimed.add(event.model_key)
        elif event.kind == "LOAD_READY":
            ready.add(event.model_key)
            assert len(ready & _HEAVY) <= 1, f"two heavy models READY at once: {ready & _HEAVY}"
        elif event.kind == "EVICT_START":
            ready.discard(event.model_key)
        elif event.kind == "EVICT_DONE":
            claimed.discard(event.model_key)


async def test_single_heavy_resident_across_swaps(manager: ModelManager) -> None:
    async with manager.acquire("brain") as lease:
        brain_pid = lease.pid
    assert brain_pid is not None

    async with manager.acquire("vlm") as lease:
        vlm_pid = lease.pid
        assert vlm_pid is not None and vlm_pid != brain_pid
        assert not _pid_alive(brain_pid), "brain process still alive after vlm acquired"
        assert _pid_alive(vlm_pid)

    async with manager.acquire("brain") as lease:
        assert lease.pid not in (brain_pid, vlm_pid)
        assert not _pid_alive(vlm_pid), "vlm process still alive after brain re-acquired"

    _assert_never_two_heavy_ready(manager.events)

    kinds = [e.kind for e in manager.events]
    for index, kind in enumerate(kinds):
        if kind == "LOAD_START":
            prior = kinds[:index]
            assert prior.count("EVICT_DONE") == prior.count("EVICT_START"), (
                "a LOAD_START occurred before the preceding eviction finished"
            )
