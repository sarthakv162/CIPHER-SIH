"""Runtime ABC for supervised model child processes, plus process and health helpers."""

from __future__ import annotations

import abc
import asyncio
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable


class Runtime(abc.ABC):
    """A model served by a child process behind a loopback HTTP endpoint."""

    key: str
    class_: str

    @property
    @abc.abstractmethod
    def pid(self) -> int | None:
        """OS process id of the running child, or None if not started."""

    @property
    @abc.abstractmethod
    def endpoint(self) -> str:
        """Base loopback URL the model answers on."""

    @abc.abstractmethod
    async def start(self) -> None:
        """Spawn the child process and block until it answers GET /health."""

    @abc.abstractmethod
    async def stop(self) -> None:
        """SIGTERM the child, then SIGKILL after the grace period. Never garbage collection."""

    @abc.abstractmethod
    async def is_healthy(self) -> bool:
        """True when GET /health returns 200."""

    @abc.abstractmethod
    def is_alive(self) -> bool:
        """True when the child process exists and has not exited."""

    def rss_bytes(self) -> int | None:
        """Resident set size of the child in bytes, best effort (None if unavailable)."""
        return read_rss_bytes(self.pid)


def http_get_status(url: str, *, timeout: float = 1.0) -> int:
    """Return the HTTP status for a loopback GET, or 0 on any connection error."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return int(response.status)
    except (urllib.error.URLError, ConnectionError, OSError, ValueError):
        return 0


async def wait_healthy(
    check: Callable[[], Awaitable[bool]],
    *,
    timeout: float,
    interval: float,
    now: Callable[[], float] = time.monotonic,
) -> bool:
    """Poll `check` until it returns True or `timeout` seconds elapse."""
    deadline = now() + timeout
    while now() < deadline:
        if await check():
            return True
        await asyncio.sleep(interval)
    return await check()


async def terminate_process(
    proc: subprocess.Popen[bytes],
    *,
    sigkill_after: float,
    poll_interval: float = 0.1,
    now: Callable[[], float] = time.monotonic,
) -> None:
    """SIGTERM the process, wait up to `sigkill_after` seconds, then SIGKILL and reap it."""
    if proc.poll() is not None:
        return
    proc.terminate()
    deadline = now() + sigkill_after
    while now() < deadline:
        if proc.poll() is not None:
            return
        await asyncio.sleep(poll_interval)
    proc.kill()
    await asyncio.to_thread(proc.wait)


def read_rss_bytes(pid: int | None) -> int | None:
    """Best-effort resident set size of a pid via `ps`; None when it cannot be read."""
    if pid is None:
        return None
    try:
        result = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = result.stdout.strip()
    return int(text) * 1024 if text.isdigit() else None
