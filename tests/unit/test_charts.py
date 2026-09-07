"""Unit coverage for render/charts.py: numeric extraction never fabricates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rupantar.render.charts import extract_chart_data, parse_leading_number, render_chart
from rupantar.render.theme import load_theme

_THEME = load_theme("ntro-formal")


@dataclass
class _Section:
    stat_value: str
    stat_label: str = "label"


@dataclass
class _Layout:
    value: str


@dataclass
class _Spec:
    headline: str
    sections: list[_Section]
    layout_recommendation: _Layout


def test_parse_leading_number() -> None:
    assert parse_leading_number("8 days") == 8.0
    assert parse_leading_number("11") == 11.0
    assert parse_leading_number("0") == 0.0
    assert parse_leading_number("90 Minutes") == 90.0
    assert parse_leading_number("1,200 endpoints") == 1200.0
    assert parse_leading_number("several") is None
    assert parse_leading_number("") is None


def test_bar_data_from_two_or_more_numeric_stats() -> None:
    spec = _Spec(
        "Incident by the numbers",
        [_Section("8 days", "to contain"), _Section("11", "regions"), _Section("no", "data")],
        _Layout("vertical_flow"),
    )
    data = extract_chart_data(spec)
    assert data is not None and data.kind == "bar"
    assert data.points == [("to contain", 8.0), ("regions", 11.0)]


def test_returns_none_when_nothing_numeric_parses() -> None:
    spec = _Spec(
        "Qualitative only",
        [_Section("high", "impact"), _Section("broad", "scope")],
        _Layout("comparison"),
    )
    assert extract_chart_data(spec) is None


def test_timeline_when_layout_is_timeline_and_no_numbers() -> None:
    spec = _Spec(
        "How it unfolded",
        [
            _Section("first", "Detection"),
            _Section("then", "Escalation"),
            _Section("last", "Recovery"),
        ],
        _Layout("timeline"),
    )
    data = extract_chart_data(spec)
    assert data is not None and data.kind == "timeline"
    assert data.labels == ["Detection", "Escalation", "Recovery"]


def test_bar_and_timeline_render_1280x720(tmp_path: Path) -> None:
    from PIL import Image

    bar = extract_chart_data(
        _Spec("b", [_Section("3 h"), _Section("9 h")], _Layout("vertical_flow"))
    )
    timeline = extract_chart_data(
        _Spec("t", [_Section("a", "One"), _Section("b", "Two")], _Layout("timeline"))
    )
    assert bar is not None and timeline is not None
    for name, data in (("bar.png", bar), ("timeline.png", timeline)):
        target = tmp_path / name
        render_chart(target, data, _THEME)
        with Image.open(target) as image:
            assert image.size == (1280, 720)
