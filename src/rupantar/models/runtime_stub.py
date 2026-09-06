"""Stub runtime: a real child process serving an OpenAI-compatible stdlib HTTP server."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from rupantar.core.errors import RuntimeStartError
from rupantar.models.runtime_base import (
    Runtime,
    http_get_status,
    terminate_process,
    wait_healthy,
)

_SIGKILL_AFTER = 3.0


def _completion_text(body: dict[str, object]) -> str:
    """Resolve the completion: env override (dir of fixtures, @file, or literal), else echo."""
    spec = os.environ.get("RUPANTAR_STUB_COMPLETION")
    if spec:
        target = Path(spec[1:] if spec.startswith("@") else spec)
        if _is_dir(target):
            name = _schema_name(body)
            if name:
                return (target / f"{name}.json").read_text(encoding="utf-8")
            return _echo(body)
        if spec.startswith("@"):
            return target.read_text(encoding="utf-8")
        return spec
    return _echo(body)


def _is_dir(path: Path) -> bool:
    """True when `path` is a directory, False for a literal completion string that is not a path."""
    try:
        return path.is_dir()
    except OSError:
        return False


def _schema_name(body: dict[str, object]) -> str:
    """The response_format.json_schema.name the caller asked for, or an empty string."""
    response_format = body.get("response_format")
    if isinstance(response_format, dict):
        json_schema = response_format.get("json_schema")
        if isinstance(json_schema, dict):
            return str(json_schema.get("name") or "")
    return ""


def _echo(body: dict[str, object]) -> str:
    """Echo the last user message, the stub's default when no fixture is configured."""
    messages = body.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("role") == "user":
                return str(message.get("content", ""))
    return ""


def _envelope(content: str) -> dict[str, object]:
    """An OpenAI-compatible non-streaming chat completion response."""
    return {
        "id": "stub-completion",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _chunks(text: str, size: int = 24) -> list[str]:
    """Split text into fixed-size pieces for streamed deltas."""
    return [text[index : index + size] for index in range(0, len(text), size)]


class _Handler(BaseHTTPRequestHandler):
    """GET /health returns 200; POST /v1/chat/completions returns an OpenAI-style envelope."""

    def log_message(self, *args: object) -> None:
        """Silence the default stderr access log."""

    def do_GET(self) -> None:
        """Health endpoint. The method name is fixed by http.server dispatch."""
        if self.path == "/health":
            self._json(200, {"status": "ok"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        """Answer a chat completion, streaming when asked. Method name fixed by dispatch."""
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            body = {}
        if self.path.split("?", 1)[0] != "/v1/chat/completions":
            self._json(404, {"error": "not found"})
            return
        content = _completion_text(body)
        if "stream" in self.path or bool(body.get("stream")):
            self._sse(content)
        else:
            self._json(200, _envelope(content))

    def _sse(self, content: str) -> None:
        """Write content as Server-Sent Events: delta frames then a stop frame and [DONE]."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        for piece in _chunks(content):
            frame = json.dumps(
                {"choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}]}
            )
            self.wfile.write(f"data: {frame}\n\n".encode())
        tail = json.dumps({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
        self.wfile.write(f"data: {tail}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _json(self, code: int, payload: dict[str, object]) -> None:
        """Write a JSON response with an explicit content length."""
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _serve(port: int) -> None:
    """Run the echo server on 127.0.0.1:port until the process is killed."""
    HTTPServer(("127.0.0.1", port), _Handler).serve_forever()


class StubRuntime(Runtime):
    """A Runtime backed by the echo server above, spawned as a separate OS process."""

    def __init__(
        self,
        *,
        key: str,
        class_: str,
        port: int,
        health_timeout: float = 10.0,
        health_interval: float = 0.05,
        spawn: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
        python_exe: str = sys.executable,
    ) -> None:
        """Configure the stub without starting it."""
        self.key = key
        self.class_ = class_
        self._port = port
        self._health_timeout = health_timeout
        self._health_interval = health_interval
        self._spawn = spawn
        self._python = python_exe
        self._proc: subprocess.Popen[bytes] | None = None

    @property
    def endpoint(self) -> str:
        """Loopback URL of the echo server."""
        return f"http://127.0.0.1:{self._port}"

    @property
    def pid(self) -> int | None:
        """Child pid, or None before start."""
        return self._proc.pid if self._proc else None

    async def start(self) -> None:
        """Spawn the echo server process and wait for GET /health."""
        self._proc = self._spawn(
            [self._python, "-m", "rupantar.models.runtime_stub", "--port", str(self._port)]
        )
        ok = await wait_healthy(
            self.is_healthy, timeout=self._health_timeout, interval=self._health_interval
        )
        if not ok:
            await self.stop()
            raise RuntimeStartError(
                f"stub runtime for {self.key!r} did not become healthy on port {self._port}; "
                "check that no other process is holding that port"
            )

    async def stop(self) -> None:
        """SIGTERM then SIGKILL-after-grace the echo server."""
        if self._proc is not None:
            await terminate_process(self._proc, sigkill_after=_SIGKILL_AFTER)

    async def is_healthy(self) -> bool:
        """True when GET /health returns 200."""
        url = self.endpoint + "/health"
        return await asyncio.to_thread(lambda: http_get_status(url) == 200)

    def is_alive(self) -> bool:
        """True while the child process has not exited."""
        return self._proc is not None and self._proc.poll() is None


def _main(argv: list[str] | None = None) -> None:
    """Entrypoint for `python -m rupantar.models.runtime_stub --port N`."""
    parser = argparse.ArgumentParser(prog="rupantar.models.runtime_stub")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args(argv)
    _serve(args.port)


if __name__ == "__main__":
    _main()
