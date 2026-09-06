"""Unit tests for the air-gap egress monitor."""

from __future__ import annotations

import pytest

from rupantar.audit.egress import (
    EgressReport,
    RemoteConnection,
    _is_loopback,
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
