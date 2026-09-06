"""Unit tests for the selfcheck report, run against the file-less test-stub profile."""

from __future__ import annotations

from pathlib import Path

import pytest

from rupantar.audit._fixtures import sample_artefacts, write_converter_samples
from rupantar.audit._selfcheck_checks import (
    _check_one_model,
    check_converters,
    check_ports,
    check_python,
    check_renderers,
)
from rupantar.audit.selfcheck import CheckResult, SelfcheckReport, run_selfcheck
from rupantar.core.config import Env, load_config
from rupantar.models.registry import ModelEntry

_CONFIGS = Path(__file__).resolve().parents[2] / "configs"


@pytest.fixture
def stub_config():  # type: ignore[no-untyped-def]
    """AppConfig pinned to the test-stub profile."""
    return load_config(_CONFIGS, env=Env(profile="test-stub"))


def test_check_python_reports_current_interpreter() -> None:
    (result,) = check_python()
    assert result.number == "1"
    assert result.level == "ok"  # the test suite must run on 3.11
    assert "3.11" in result.data["python"]


def test_check_ports_finds_free_ports(stub_config) -> None:  # type: ignore[no-untyped-def]
    (result,) = check_ports(stub_config)
    assert result.number == "4"
    assert result.data["free"] > 0


def test_sample_artefacts_all_valid() -> None:
    arts = sample_artefacts()
    assert set(arts) == {
        "executive_summary",
        "advisory",
        "linkedin_post",
        "x_thread",
        "presentation",
        "infographic_spec",
        "video_package",
    }


def test_check_renderers_all_ok() -> None:
    results = check_renderers()
    assert len(results) == 7
    assert all(r.level == "ok" for r in results), [(r.name, r.detail) for r in results]


def test_check_converters_round_trip_ok() -> None:
    results = check_converters()
    assert {r.name for r in results} == {
        "convert: csv",
        "convert: ioc-csv",
        "convert: sigma",
        "convert: cef",
    }
    assert all(r.level == "ok" for r in results), [(r.name, r.detail) for r in results]


def test_write_converter_samples(tmp_path: Path) -> None:
    paths = write_converter_samples(tmp_path)
    assert all(p.is_file() for p in paths.values())


def test_missing_model_file_is_a_red_row() -> None:
    entry = ModelEntry(
        key="brain",
        class_="heavy",
        runtime="llama",
        path=Path("models/brain/does-not-exist.gguf"),
    )
    result = _check_one_model(entry, fast=True)
    assert result.number == "3"
    assert result.level == "fail"
    assert "fetch_models.sh" in result.detail


def test_report_with_a_failing_check_signals_failure() -> None:
    report = SelfcheckReport(
        generated_at="2026-09-07T00:00:00+00:00",
        profile="apple-metal",
        profile_source="auto-detect",
        checks=[
            CheckResult(number="1", name="python + platform", level="ok", detail="fine"),
            CheckResult(number="3", name="model: brain", level="fail", detail="SHA-256 mismatch"),
        ],
    )
    assert report.ok is False
    assert report.result == "FAIL"
    assert report.exit_code == 1
    assert "result: FAIL" in report.table()
    dumped = report.model_dump()
    assert dumped["ok"] is False and dumped["result"] == "FAIL"
    assert '"ok":false' in report.model_dump_json().replace(" ", "")


def test_run_selfcheck_stub_profile_passes(stub_config) -> None:  # type: ignore[no-untyped-def]
    report = run_selfcheck(config=stub_config, fast=True)
    numbers = [c.number for c in report.checks]
    for expected in ("1", "2", "3", "4", "4b", "5", "6", "7", "8"):
        assert expected in numbers, f"missing check {expected}"
    assert isinstance(report.checks[0], CheckResult)
    assert "selfcheck" in report.table()
    # model-file and offload checks are stub no-ops; nothing here should hard-fail
    non_tool_fails = [c for c in report.checks if c.level == "fail" and c.number != "2"]
    assert not non_tool_fails, [(c.name, c.detail) for c in non_tool_fails]
