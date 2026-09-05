"""The stub runtime spawns a real child process that answers /health and echoes POSTs."""

from __future__ import annotations

import json
import os
import urllib.request

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


async def test_chat_completions_echoes_body() -> None:
    runtime = await _started()
    try:
        payload = json.dumps({"messages": [{"role": "user", "content": "hi"}]}).encode()
        request = urllib.request.Request(
            runtime.endpoint + "/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            body = json.loads(response.read())
        assert body["echo"]["messages"][0]["content"] == "hi"
        assert body["path"] == "/v1/chat/completions"
    finally:
        await runtime.stop()


def test_find_free_port_respects_exclusions() -> None:
    first = find_free_port(8100, 8199)
    second = find_free_port(8100, 8199, exclude={first})
    assert first != second
