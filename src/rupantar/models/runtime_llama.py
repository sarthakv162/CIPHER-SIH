"""llama-server subprocess runtime. Real-binary behaviour is exercised only under -m slow."""

from __future__ import annotations

import asyncio
import subprocess
from collections.abc import Callable, Sequence

from rupantar.core.errors import RuntimeStartError
from rupantar.models.registry import ModelEntry
from rupantar.models.runtime_base import (
    Runtime,
    http_get_status,
    terminate_process,
    wait_healthy,
)

_SIGKILL_AFTER = 10.0


def _as_list(args: object) -> list[object]:
    """Normalise a YAML args value (list or dict) into a flat argv fragment."""
    if isinstance(args, dict):
        fragment: list[object] = []
        for key, value in args.items():
            fragment += [f"--{key}", value]
        return fragment
    if isinstance(args, list | tuple):
        return list(args)
    return []


class LlamaRuntime(Runtime):
    """Runs `llama-server` for one GGUF model on a loopback port."""

    def __init__(
        self,
        *,
        entry: ModelEntry,
        port: int,
        binary: str = "llama-server",
        host: str = "127.0.0.1",
        common_args: Sequence[str] = (),
        health_timeout: float = 120.0,
        health_interval: float = 0.5,
        spawn: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
    ) -> None:
        """Configure the llama-server invocation without starting it."""
        self.key = entry.key
        self.class_ = entry.class_
        self._entry = entry
        self._port = port
        self._binary = binary
        self._host = host
        self._common_args = list(common_args)
        self._health_timeout = health_timeout
        self._health_interval = health_interval
        self._spawn = spawn
        self._proc: subprocess.Popen[bytes] | None = None

    @property
    def endpoint(self) -> str:
        """Loopback base URL for the OpenAI-compatible server."""
        return f"http://{self._host}:{self._port}"

    @property
    def pid(self) -> int | None:
        """Child pid, or None before start."""
        return self._proc.pid if self._proc else None

    def _command(self) -> list[str]:
        """Full argv for llama-server."""
        if self._entry.path is None:
            raise RuntimeStartError(
                f"model {self.key!r} has no file path; run scripts/fetch_models.sh while online"
            )
        cmd = [
            self._binary,
            "-m",
            str(self._entry.path),
            "--host",
            self._host,
            "--port",
            str(self._port),
        ]
        mmproj = self._entry.extra.get("mmproj")
        if mmproj:
            cmd += ["--mmproj", str(mmproj)]
        cmd += self._common_args
        cmd += [str(a) for a in _as_list(self._entry.args)]
        return cmd

    async def start(self) -> None:
        """Spawn llama-server and poll GET /health until it is ready."""
        self._proc = self._spawn(self._command())
        ok = await wait_healthy(
            self.is_healthy, timeout=self._health_timeout, interval=self._health_interval
        )
        if not ok:
            await self.stop()
            raise RuntimeStartError(
                f"llama-server for {self.key!r} did not report healthy within "
                f"{self._health_timeout:g}s on port {self._port}; check the binary and GGUF file"
            )

    async def stop(self) -> None:
        """SIGTERM llama-server, then SIGKILL after a 10-second grace."""
        if self._proc is not None:
            await terminate_process(self._proc, sigkill_after=_SIGKILL_AFTER)

    async def is_healthy(self) -> bool:
        """True when GET /health returns 200."""
        url = self.endpoint + "/health"
        return await asyncio.to_thread(lambda: http_get_status(url) == 200)

    def is_alive(self) -> bool:
        """True while llama-server has not exited."""
        return self._proc is not None and self._proc.poll() is None
