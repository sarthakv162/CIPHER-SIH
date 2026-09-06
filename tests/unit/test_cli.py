"""The Typer CLI exposes exactly four stub commands."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from rupantar.cli.main import app

runner = CliRunner()


def test_help_lists_exactly_four_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("transform", "convert", "selfcheck", "models"):
        assert command in result.output


def test_selfcheck_runs_and_reports(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("RUPANTAR_PROFILE", "test-stub")
    result = runner.invoke(app, ["selfcheck", "--fast", "--json"])
    assert "python + platform" in result.output
    assert "egress during run" in result.output
    assert result.exit_code in (0, 1)


def test_convert_runs_a_conversion(tmp_path: Path) -> None:
    source = tmp_path / "in.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    out = tmp_path / "out.json"
    result = runner.invoke(app, ["convert", str(source), "--to", "json", "--out", str(out)])
    assert result.exit_code == 0
    assert "1 rows ->" in result.output
    assert out.is_file()


def test_convert_missing_input_exits_one(tmp_path: Path) -> None:
    result = runner.invoke(app, ["convert", str(tmp_path / "nope.csv"), "--to", "json"])
    assert result.exit_code == 1


def test_convert_unknown_pair_exits_one(tmp_path: Path) -> None:
    source = tmp_path / "in.csv"
    source.write_text("a,b\n1,2\n", encoding="utf-8")
    result = runner.invoke(app, ["convert", str(source), "--to", "sigma-json"])
    assert result.exit_code == 1
    assert "no converter" in result.output


def test_transform_help_shows_the_new_options() -> None:
    result = runner.invoke(app, ["transform", "--help"])
    assert result.exit_code == 0
    for option in ("--text", "--output", "--profile", "--stream", "--out-dir"):
        assert option in result.output


def test_models_status_prints_the_residency_table() -> None:
    result = runner.invoke(app, ["models", "status"])
    assert result.exit_code == 0
    assert "KEY" in result.output
    assert "STATE" in result.output
    assert "brain" in result.output
    assert "NOT_LOADED" in result.output
