"""INV-8: Unload is OS process termination, never a Python garbage-collection hope."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from rupantar.core.config import Env, load_config
from rupantar.models.manager import ModelManager
from rupantar.models.registry import Registry

_CONFIGS = Path(__file__).resolve().parents[2] / "configs"


def _manager() -> ModelManager:
    config = load_config(_CONFIGS, env=Env(profile="test-stub", db=None))
    registry = Registry.from_config(config, verify=False)
    return ModelManager(registry, policy={"port_range": [8100, 8199]})


@pytest.fixture
async def manager() -> AsyncIterator[ModelManager]:
    mgr = _manager()
    try:
        yield mgr
    finally:
        await mgr.aclose()


async def _wait_gone(pid: int, *, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        await asyncio.sleep(0.05)
    return False


async def test_unload_is_a_real_process_death(manager: ModelManager) -> None:
    lease = await manager.obtain("brain")
    pid = lease.pid
    assert pid is not None
    os.kill(pid, 0)  # alive while leased

    await lease.release()
    await manager.evict("brain")

    assert await _wait_gone(pid), "model child process survived unload"
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)

    evict_done = [e for e in manager.events if e.kind == "EVICT_DONE" and e.model_key == "brain"]
    assert evict_done and evict_done[-1].pid == pid
