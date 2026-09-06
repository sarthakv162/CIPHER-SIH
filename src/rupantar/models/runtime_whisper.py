"""faster-whisper worker subprocess and its Runtime. No heavy import at module scope (INV-1)."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import signal
import subprocess
import sys
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from rupantar.core.errors import RuntimeStartError
from rupantar.models.registry import ModelEntry
from rupantar.models.runtime_base import (
    Runtime,
    http_get_status,
    terminate_process,
    wait_healthy,
)

_SIGKILL_AFTER = 10.0
_STATE: dict[str, Any] = {}


class WhisperRuntime(Runtime):
    """Runs the faster-whisper worker for one CTranslate2 model directory on a loopback port."""

    def __init__(
        self,
        *,
        entry: ModelEntry,
        port: int,
        host: str = "127.0.0.1",
        health_timeout: float = 120.0,
        health_interval: float = 0.5,
        spawn: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
        python_exe: str = sys.executable,
    ) -> None:
        """Configure the worker invocation without starting it."""
        self.key = entry.key
        self.class_ = entry.class_
        self._entry = entry
        self._port = port
        self._host = host
        self._health_timeout = health_timeout
        self._health_interval = health_interval
        self._spawn = spawn
        self._python = python_exe
        self._proc: subprocess.Popen[bytes] | None = None

    @property
    def endpoint(self) -> str:
        """Loopback base URL for the transcription worker."""
        return f"http://{self._host}:{self._port}"

    @property
    def pid(self) -> int | None:
        """Child pid, or None before start."""
        return self._proc.pid if self._proc else None

    def _command(self) -> list[str]:
        """Full argv for the worker process."""
        if self._entry.path is None:
            raise RuntimeStartError(
                f"model {self.key!r} has no path; add it to models.yaml or run "
                "scripts/fetch_models.sh while online"
            )
        opts = self._entry.args if isinstance(self._entry.args, dict) else {}
        return [
            self._python,
            "-m",
            "rupantar.models.runtime_whisper",
            "--port",
            str(self._port),
            "--model",
            str(self._entry.path),
            "--compute-type",
            str(opts.get("compute_type", "int8")),
            "--beam-size",
            str(opts.get("beam_size", 1)),
        ]

    async def start(self) -> None:
        """Spawn the worker and poll GET /health until the model has loaded."""
        self._proc = self._spawn(self._command())
        ok = await wait_healthy(
            self.is_healthy, timeout=self._health_timeout, interval=self._health_interval
        )
        if not ok:
            await self.stop()
            raise RuntimeStartError(
                f"whisper worker for {self.key!r} did not report healthy within "
                f"{self._health_timeout:g}s on port {self._port}; check the model directory "
                f"{self._entry.path} contains model.bin + config.json + tokenizer.json"
            )

    async def stop(self) -> None:
        """SIGTERM the worker, then SIGKILL after a 10-second grace."""
        if self._proc is not None:
            await terminate_process(self._proc, sigkill_after=_SIGKILL_AFTER)

    async def is_healthy(self) -> bool:
        """True when GET /health returns 200."""
        url = self.endpoint + "/health"
        return await asyncio.to_thread(lambda: http_get_status(url) == 200)

    def is_alive(self) -> bool:
        """True while the worker process has not exited."""
        return self._proc is not None and self._proc.poll() is None


class _Handler(BaseHTTPRequestHandler):
    """GET /health -> 200 once loaded; POST /transcribe -> {text, segments}."""

    def log_message(self, *args: object) -> None:
        """Silence the default stderr access log."""

    def do_GET(self) -> None:
        """Health endpoint. Method name is fixed by http.server dispatch."""
        if self.path == "/health" and _STATE.get("model") is not None:
            self._json(200, {"status": "ok"})
        else:
            self._json(503, {"status": "loading"})

    def do_POST(self) -> None:
        """Transcribe the audio file named in the body. Method name fixed by dispatch."""
        if self.path.split("?", 1)[0] != "/transcribe":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            body = {}
        audio_path = body.get("audio_path")
        if not audio_path:
            self._json(400, {"error": "audio_path is required"})
            return
        try:
            self._json(200, _transcribe_file(str(audio_path)))
        except Exception as exc:  # noqa: BLE001 - report any worker failure as HTTP 500
            self._json(500, {"error": f"{type(exc).__name__}: {exc}"})

    def _json(self, code: int, payload: dict[str, Any]) -> None:
        """Write a JSON response with an explicit content length."""
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _transcribe_file(audio_path: str) -> dict[str, Any]:
    """Run the loaded model over one audio file and return text plus timed segments."""
    model = _STATE["model"]
    segments, _info = model.transcribe(audio_path, beam_size=_STATE["beam_size"])
    seg_out: list[dict[str, Any]] = []
    texts: list[str] = []
    for seg in segments:
        seg_out.append(
            {"start": round(float(seg.start), 3), "end": round(float(seg.end), 3), "text": seg.text}
        )
        texts.append(seg.text)
    return {"text": "".join(texts).strip(), "segments": seg_out}


def _serve(port: int, model_dir: str, compute_type: str, beam_size: int) -> None:
    """Load the model from a local directory only, then serve until the process is killed."""
    from faster_whisper import WhisperModel

    # SIGTERM (the manager's first stop signal) -> clean exit so CTranslate2's worker
    # pool releases its semaphores instead of leaking on the SIGKILL that follows.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    _STATE["model"] = WhisperModel(
        model_dir, device="cpu", compute_type=compute_type, local_files_only=True
    )
    _STATE["beam_size"] = beam_size
    server = HTTPServer(("127.0.0.1", port), _Handler)
    with contextlib.suppress(SystemExit):
        server.serve_forever()


def _main(argv: list[str] | None = None) -> None:
    """Entrypoint for `python -m rupantar.models.runtime_whisper`."""
    parser = argparse.ArgumentParser(prog="rupantar.models.runtime_whisper")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--beam-size", type=int, default=1)
    args = parser.parse_args(argv)
    _serve(args.port, args.model, args.compute_type, args.beam_size)


if __name__ == "__main__":
    _main()
