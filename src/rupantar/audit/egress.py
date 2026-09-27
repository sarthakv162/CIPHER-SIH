"""Air-gap enforcement: offline env vars plus a psutil egress monitor over our process tree."""

from __future__ import annotations

import ipaddress
import logging
import os
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import psutil

from rupantar.core.errors import EgressViolationError

_LOG = logging.getLogger("rupantar.egress")

OFFLINE_ENV: dict[str, str] = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "NO_PROXY": "*",
}

_LOOPBACK_NETS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
)


def enforce_offline_env(environ: MutableMapping[str, str] | None = None) -> dict[str, str]:
    """Set the offline env vars in `environ`, assert they took, and return the applied set."""
    env = os.environ if environ is None else environ
    for key, value in OFFLINE_ENV.items():
        env[key] = value
    missing = [k for k, v in OFFLINE_ENV.items() if env.get(k) != v]
    if missing:
        raise EgressViolationError(
            f"offline env vars did not apply: {missing}; the process environment is read-only"
        )
    return dict(OFFLINE_ENV)


def _is_loopback(host: str) -> bool:
    """True when `host` is empty, unspecified, or inside a loopback network."""
    if not host or host in ("0.0.0.0", "::", "*"):
        return True
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(addr in net for net in _LOOPBACK_NETS)


@dataclass(frozen=True)
class RemoteConnection:
    """One socket held by our process tree with a non-loopback (or any) remote peer."""

    pid: int
    process: str
    laddr: str
    raddr: str
    status: str

    def as_dict(self) -> dict[str, object]:
        """JSON-friendly view for the /health/egress route and manifests."""
        return {
            "pid": self.pid,
            "process": self.process,
            "laddr": self.laddr,
            "raddr": self.raddr,
            "status": self.status,
        }


@dataclass
class EgressReport:
    """The result of one egress scan over the current process tree."""

    checked_at: str
    scanned_pids: list[int] = field(default_factory=list)
    violations: list[RemoteConnection] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        """True when no non-loopback remote connection was seen."""
        return not self.violations

    def as_dict(self) -> dict[str, object]:
        """JSON-friendly view for the /health/egress route."""
        return {
            "checked_at": self.checked_at,
            "clean": self.clean,
            "scanned_pids": self.scanned_pids,
            "violations": [v.as_dict() for v in self.violations],
        }


_ACCUMULATED: list[RemoteConnection] = []


def _tree_processes(root_pid: int | None) -> list[psutil.Process]:
    """The current process (or `root_pid`) plus every live descendant."""
    try:
        root = psutil.Process(root_pid)
    except psutil.Error:
        return []
    procs = [root]
    try:
        procs.extend(root.children(recursive=True))
    except psutil.Error:
        pass
    return procs


def _addr(pair: object) -> str:
    """Render a psutil addr tuple as host:port, or '' when absent."""
    if not pair:
        return ""
    host = getattr(pair, "ip", "")
    port = getattr(pair, "port", "")
    return f"{host}:{port}" if port else str(host)


def _listening_ports(conns: list[Any]) -> set[int]:
    """Local ports our process tree is accepting connections on."""
    return {conn.laddr.port for conn in conns if conn.status == psutil.CONN_LISTEN and conn.laddr}


def _is_egress(conn: Any, listening: set[int]) -> bool:
    """True for an outbound socket to a non-loopback peer; inbound accepts are not egress."""
    remote_host = getattr(conn.raddr, "ip", "") if conn.raddr else ""
    if _is_loopback(remote_host):
        return False
    return not (conn.laddr and conn.laddr.port in listening)


def scan_egress(root_pid: int | None = None) -> EgressReport:
    """Scan our process tree's sockets; flag every outbound connection to a non-loopback peer.

    A client connected to one of our own listening ports (a browser reaching the API through a
    container port-forward, say) is ingress, not egress, and is not flagged.
    """
    report = EgressReport(checked_at=datetime.now(UTC).isoformat())
    per_proc: list[tuple[psutil.Process, str, list[Any]]] = []
    for proc in _tree_processes(root_pid):
        try:
            per_proc.append((proc, proc.name(), proc.net_connections(kind="inet")))
        except psutil.Error:
            continue
    listening = _listening_ports([c for _, _, conns in per_proc for c in conns])
    for proc, name, conns in per_proc:
        report.scanned_pids.append(proc.pid)
        for conn in conns:
            if not _is_egress(conn, listening):
                continue
            report.violations.append(
                RemoteConnection(
                    pid=proc.pid,
                    process=name,
                    laddr=_addr(conn.laddr),
                    raddr=_addr(conn.raddr),
                    status=str(conn.status),
                )
            )
    if report.violations:
        _record(report.violations)
    return report


def _record(violations: list[RemoteConnection]) -> None:
    """Log each violation once and keep it for GET /health/egress."""
    for v in violations:
        _LOG.error(
            "EGRESS_VIOLATION pid=%s process=%s laddr=%s raddr=%s status=%s",
            v.pid,
            v.process,
            v.laddr,
            v.raddr,
            v.status,
        )
    _ACCUMULATED.extend(violations)


def accumulated_violations() -> list[RemoteConnection]:
    """Every non-loopback connection seen since the process started."""
    return list(_ACCUMULATED)


def clear_accumulated() -> None:
    """Forget accumulated violations (tests only)."""
    _ACCUMULATED.clear()


def assert_clean(report: EgressReport, *, strict: bool) -> None:
    """Raise EgressViolationError when `strict` and the report is not clean."""
    if strict and not report.clean:
        remotes = sorted({v.raddr for v in report.violations})
        raise EgressViolationError(
            f"non-loopback network connection while --strict-airgap is set: {remotes}; "
            "cut the network or drop --strict-airgap",
            remotes=remotes,
        )
