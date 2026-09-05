"""Free TCP port discovery within a configured range, loopback only."""

from __future__ import annotations

import socket
from collections.abc import Iterable

from rupantar.core.errors import NoFreePortError


def find_free_port(
    low: int, high: int, *, exclude: Iterable[int] = (), host: str = "127.0.0.1"
) -> int:
    """Return the first port in [low, high] that binds on `host` and is not excluded."""
    taken = set(exclude)
    for port in range(low, high + 1):
        if port in taken:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
        return port
    raise NoFreePortError(
        f"no free TCP port in range [{low}, {high}]; widen policy.yaml:port_range "
        "or stop stray processes holding those ports"
    )
