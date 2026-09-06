"""LlamaClient against a local http.server: content, grammar passthrough, retry, errors."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from rupantar.core.errors import ModelClientError
from rupantar.models._ports import find_free_port
from rupantar.models.client import LlamaClient


class _State:
    mode = "ok"
    reset_budget = 0
    bodies: list[dict] = []


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        _State.bodies.append(json.loads(raw or b"{}"))
        if _State.reset_budget > 0:
            _State.reset_budget -= 1
            self.close_connection = True
            self.connection.close()
            return
        if _State.mode == "http-400":
            self._send(400, b'{"error": "bad request"}')
            return
        if _State.mode == "stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for piece in ("Hel", "lo ", "wor", "ld"):
                frame = json.dumps({"choices": [{"delta": {"content": piece}}]})
                self.wfile.write(f"data: {frame}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            return
        payload = {
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "pong"},
                    "finish_reason": "stop",
                }
            ]
        }
        self._send(200, json.dumps(payload).encode())

    def _send(self, code: int, data: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def server() -> Iterator[str]:
    _State.mode = "ok"
    _State.reset_budget = 0
    _State.bodies = []
    port = find_free_port(8100, 8199)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


async def test_complete_returns_message_content(server: str) -> None:
    async with LlamaClient(server) as client:
        out = await client.complete(
            [{"role": "user", "content": "ping"}], max_tokens=16, temperature=0.0
        )
    assert out == "pong"


async def test_grammar_is_forwarded_in_the_request_body(server: str) -> None:
    async with LlamaClient(server) as client:
        await client.complete(
            [{"role": "user", "content": "x"}],
            grammar='root ::= "x"',
            max_tokens=8,
            temperature=0.0,
        )
    assert _State.bodies[-1]["grammar"] == 'root ::= "x"'


async def test_retries_once_on_connection_reset(server: str) -> None:
    _State.reset_budget = 1
    async with LlamaClient(server) as client:
        out = await client.complete(
            [{"role": "user", "content": "x"}], max_tokens=8, temperature=0.0
        )
    assert out == "pong"
    assert len(_State.bodies) == 2


async def test_http_error_raises_model_client_error(server: str) -> None:
    _State.mode = "http-400"
    async with LlamaClient(server) as client:
        with pytest.raises(ModelClientError) as excinfo:
            await client.complete([{"role": "user", "content": "x"}], max_tokens=8, temperature=0.0)
    assert excinfo.value.status == 400


async def test_stream_yields_content_deltas(server: str) -> None:
    _State.mode = "stream"
    async with LlamaClient(server) as client:
        chunks = [
            chunk
            async for chunk in client.stream(
                [{"role": "user", "content": "x"}], max_tokens=8, temperature=0.0
            )
        ]
    assert "".join(chunks) == "Hello world"
