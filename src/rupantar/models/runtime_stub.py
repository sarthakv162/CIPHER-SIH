"""Stub runtime: a real child process running a stdlib HTTP echo server. No model files."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer

from rupantar.core.errors import RuntimeStartError
from rupantar.models.runtime_base import (
    Runtime,
    http_get_status,
    terminate_process,
    wait_healthy,
)

_SIGKILL_AFTER = 3.0


class _Handler(BaseHTTPRequestHandler):
    """Answers GET /health with 200 and echoes POST /v1/chat/completions."""

    def log_message(self, *args: object) -> None:
        """Silence the default stderr access log."""

    def do_GET(self) -> None:
        """Health endpoint. The method name is fixed by http.server dispatch."""
        if self.path == "/health":
            self._json(200, {"status": "ok"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        """Echo the posted JSON body. The method name is fixed by http.server dispatch."""
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            body = {"raw": raw.decode("utf-8", "replace")}
        self._json(200, {"echo": body, "path": self.path})

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
