"""The Typer CLI exposes exactly four stub commands."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from rupantar.cli.main import app

runner = CliRunner()


def test_help_lists_exactly_four_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("transform", "convert", "selfcheck", "models"):
        assert command in result.output


@pytest.mark.parametrize(
    ("args", "needle"),
    [
        (["convert"], "phase 5"),
        (["selfcheck"], "phase 8"),
    ],
)
def test_stub_commands_exit_zero(args: list[str], needle: str) -> None:
    result = runner.invoke(app, args)
    assert result.exit_code == 0
    assert needle in result.output
    assert "not implemented" in result.output


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
