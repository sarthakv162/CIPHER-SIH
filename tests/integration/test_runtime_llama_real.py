"""Real llama-server boot. Skips unless the binary and the brain GGUF are present."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from rupantar.models.registry import ModelEntry
from rupantar.models.runtime_llama import LlamaRuntime

pytestmark = pytest.mark.slow

_REPO = Path(__file__).resolve().parents[2]
_BRAIN = _REPO / "models" / "brain" / "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"


@pytest.mark.skipif(
    shutil.which("llama-server") is None or not _BRAIN.is_file(),
    reason="needs llama-server on PATH and the brain GGUF on disk",
)
async def test_real_llama_server_boots_and_dies() -> None:
    """A real llama-server reaches healthy, then SIGTERM leaves no live process."""
    entry = ModelEntry(
        key="brain",
        class_="heavy",
        runtime="llama",
        path=_BRAIN,
        args=["--ctx-size", "2048"],
        extra={},
    )
    runtime = LlamaRuntime(
        entry=entry,
        port=8191,
        common_args=["--no-webui", "--log-disable"],
        health_timeout=120.0,
    )
    await runtime.start()
    assert runtime.is_alive()
    assert await runtime.is_healthy()
    pid = runtime.pid
    assert pid is not None
    await runtime.stop()
    assert not runtime.is_alive()
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
