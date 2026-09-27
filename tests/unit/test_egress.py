"""Unit tests for the air-gap egress monitor."""

from __future__ import annotations

from types import SimpleNamespace

import psutil
import pytest

from rupantar.audit.egress import (
    EgressReport,
    RemoteConnection,
    _is_egress,
    _is_loopback,
    _listening_ports,
    assert_clean,
    enforce_offline_env,
    scan_egress,
)
from rupantar.core.errors import EgressViolationError


def test_enforce_offline_env_sets_and_returns() -> None:
    env: dict[str, str] = {}
    applied = enforce_offline_env(env)
    assert env["HF_HUB_OFFLINE"] == "1"
    assert env["TRANSFORMERS_OFFLINE"] == "1"
    assert env["NO_PROXY"] == "*"
    assert applied["HF_HUB_OFFLINE"] == "1"


@pytest.mark.parametrize(
    ("host", "loop"),
    [
        ("127.0.0.1", True),
        ("127.5.5.5", True),
        ("::1", True),
        ("", True),
        ("0.0.0.0", True),
        ("8.8.8.8", False),
        ("192.168.1.4", False),
        ("2606:4700:4700::1111", False),
    ],
)
def test_is_loopback(host: str, loop: bool) -> None:
    assert _is_loopback(host) is loop


def test_scan_egress_on_this_process_is_clean() -> None:
    report = scan_egress()
    assert isinstance(report, EgressReport)
    assert report.clean, [v.raddr for v in report.violations]
    assert report.scanned_pids


def test_assert_clean_raises_only_when_strict_and_dirty() -> None:
    dirty = EgressReport(
        checked_at="now",
        violations=[
            RemoteConnection(
                pid=1, process="x", laddr="127.0.0.1:5", raddr="8.8.8.8:443", status="ESTABLISHED"
            )
        ],
    )
    assert_clean(dirty, strict=False)
    with pytest.raises(EgressViolationError):
        assert_clean(dirty, strict=True)
    assert_clean(EgressReport(checked_at="now"), strict=True)


def _conn(lport: int, rhost: str, rport: int, status: str) -> SimpleNamespace:
    raddr = SimpleNamespace(ip=rhost, port=rport) if rhost else ()
    return SimpleNamespace(
        laddr=SimpleNamespace(ip="172.18.0.2", port=lport), raddr=raddr, status=status
    )


def test_inbound_client_on_our_listening_port_is_not_egress() -> None:
    listen = _conn(8000, "", 0, psutil.CONN_LISTEN)
    inbound = _conn(8000, "172.18.0.3", 51544, psutil.CONN_ESTABLISHED)
    outbound = _conn(51900, "93.184.216.34", 443, psutil.CONN_ESTABLISHED)
    listening = _listening_ports([listen, inbound, outbound])
    assert listening == {8000}
    assert not _is_egress(listen, listening)
    assert not _is_egress(inbound, listening)
    assert _is_egress(outbound, listening)


def test_non_loopback_peer_is_egress_when_nothing_listens() -> None:
    assert _is_egress(_conn(8000, "172.18.0.3", 51544, psutil.CONN_ESTABLISHED), set())
