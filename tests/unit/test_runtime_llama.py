"""LlamaRuntime: argv construction (fast) and a real boot (slow, needs the binary + GGUF)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from rupantar.models.registry import ModelEntry
from rupantar.models.runtime_llama import LlamaRuntime, _as_list


def _entry(**overrides: object) -> ModelEntry:
    base: dict[str, object] = {
        "key": "brain",
        "class_": "heavy",
        "runtime": "llama",
        "path": Path("models/brain/x.gguf"),
        "args": ["--ctx-size", "8192"],
        "extra": {},
    }
    base.update(overrides)
    return ModelEntry(**base)  # type: ignore[arg-type]


def test_command_has_model_host_and_port() -> None:
    runtime = LlamaRuntime(entry=_entry(), port=8123, common_args=["--no-webui"])
    cmd = runtime._command()
    assert cmd[0] == "llama-server"
    assert cmd[cmd.index("-m") + 1] == "models/brain/x.gguf"
    assert cmd[cmd.index("--port") + 1] == "8123"
    assert cmd[cmd.index("--host") + 1] == "127.0.0.1"
    assert "--no-webui" in cmd
    assert cmd[cmd.index("--ctx-size") + 1] == "8192"


def test_command_adds_mmproj_when_present() -> None:
    runtime = LlamaRuntime(entry=_entry(extra={"mmproj": "models/vlm/mm.gguf"}), port=8124)
    cmd = runtime._command()
    assert cmd[cmd.index("--mmproj") + 1] == "models/vlm/mm.gguf"


def test_endpoint_is_loopback() -> None:
    assert LlamaRuntime(entry=_entry(), port=8125).endpoint == "http://127.0.0.1:8125"


def test_as_list_normalises_dict_and_list() -> None:
    assert _as_list({"compute_type": "int8"}) == ["--compute_type", "int8"]
    assert _as_list(["--a", "1"]) == ["--a", "1"]
    assert _as_list(None) == []


@pytest.mark.slow
async def test_real_llama_server_boots_and_dies() -> None:
    if shutil.which("llama-server") is None:
        pytest.skip("llama-server binary not installed")
    pytest.skip("no GGUF file on disk in phase 1")
