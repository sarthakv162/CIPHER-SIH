"""The stub runtime spawns a real child process that answers /health and echoes POSTs."""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

import pytest

from rupantar.models._ports import find_free_port
from rupantar.models.runtime_stub import StubRuntime


async def _started() -> StubRuntime:
    runtime = StubRuntime(key="brain", class_="heavy", port=find_free_port(8100, 8199))
    await runtime.start()
    return runtime


async def test_start_spawns_child_and_reports_health() -> None:
    runtime = await _started()
    try:
        assert runtime.pid is not None
        os.kill(runtime.pid, 0)
        assert runtime.is_alive()
        assert await runtime.is_healthy()
        assert runtime.endpoint.startswith("http://127.0.0.1:")
    finally:
        await runtime.stop()


async def test_stop_terminates_the_process() -> None:
    runtime = await _started()
    pid = runtime.pid
    assert pid is not None
    await runtime.stop()
    assert not runtime.is_alive()
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def _post(endpoint: str, payload: dict[str, object]) -> dict[str, object]:
    request = urllib.request.Request(
        endpoint + "/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        result: dict[str, object] = json.loads(response.read())
    return result


async def test_chat_completions_returns_openai_envelope() -> None:
    runtime = await _started()
    try:
        body = _post(runtime.endpoint, {"messages": [{"role": "user", "content": "hi there"}]})
        choice = body["choices"][0]  # type: ignore[index]
        assert choice["message"]["content"] == "hi there"
        assert choice["finish_reason"] == "stop"
    finally:
        await runtime.stop()


async def test_chat_completions_uses_canned_env_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUPANTAR_STUB_COMPLETION", "canned-value")
    runtime = StubRuntime(key="brain", class_="heavy", port=find_free_port(8100, 8199))
    await runtime.start()
    try:
        body = _post(runtime.endpoint, {"messages": []})
        assert body["choices"][0]["message"]["content"] == "canned-value"  # type: ignore[index]
    finally:
        await runtime.stop()


async def test_chat_completions_reads_named_fixture_from_a_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "advisory.json").write_text('{"picked": "advisory"}', encoding="utf-8")
    monkeypatch.setenv("RUPANTAR_STUB_COMPLETION", str(tmp_path))
    runtime = StubRuntime(key="brain", class_="heavy", port=find_free_port(8100, 8199))
    await runtime.start()
    try:
        body = _post(
            runtime.endpoint,
            {
                "messages": [],
                "response_format": {"type": "json_schema", "json_schema": {"name": "advisory"}},
            },
        )
        content = body["choices"][0]["message"]["content"]  # type: ignore[index]
        assert json.loads(content) == {"picked": "advisory"}
    finally:
        await runtime.stop()


async def test_directory_spec_without_schema_name_falls_back_to_echo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUPANTAR_STUB_COMPLETION", str(tmp_path))
    runtime = StubRuntime(key="brain", class_="heavy", port=find_free_port(8100, 8199))
    await runtime.start()
    try:
        body = _post(runtime.endpoint, {"messages": [{"role": "user", "content": "echo me"}]})
        assert body["choices"][0]["message"]["content"] == "echo me"  # type: ignore[index]
    finally:
        await runtime.stop()


def test_find_free_port_respects_exclusions() -> None:
    first = find_free_port(8100, 8199)
    second = find_free_port(8100, 8199, exclude={first})
    assert first != second
