"""Phase 5: the general tabular converter matrix and its round-trip guarantees."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from rupantar.core.errors import ConversionError
from rupantar.parivartan.registry import convert, list_conversions

_FORMATS = ["csv", "tsv", "json", "jsonl", "yaml", "xml", "xlsx", "parquet"]


@pytest.fixture
def clean_csv(fixtures_dir: Path) -> Path:
    """A quirk-free CSV used for round-trip assertions."""
    return fixtures_dir / "parivartan" / "clean.csv"


@pytest.fixture
def messy_csv(fixtures_dir: Path) -> Path:
    """A CSV with a BOM, quoted commas/newlines, a blank line, a short and a long row."""
    return fixtures_dir / "parivartan" / "messy.csv"


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Return (header, rows) from a CSV file."""
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def test_list_conversions_covers_matrix_and_bespoke() -> None:
    """Every general reader x writer pair plus the cyber converters are catalogued."""
    pairs = {(entry["src"], entry["dst"]) for entry in list_conversions()}
    for src in _FORMATS:
        for dst in _FORMATS:
            assert (src, dst) in pairs
    for bespoke in (
        ("ioc-csv", "stix21"),
        ("stix21", "ioc-csv"),
        ("sigma", "sigma-json"),
        ("cef", "jsonl"),
    ):
        assert bespoke in pairs


def test_csv_json_csv_round_trip_preserves_rows_and_order(clean_csv: Path, tmp_path: Path) -> None:
    """csv -> json -> csv keeps row count and exact column order, values unchanged."""
    original_header, original_rows = _read_csv_rows(clean_csv)

    as_json = tmp_path / "mid.json"
    report_a = convert(clean_csv, "csv", "json", as_json)
    assert report_a.ok and report_a.rows == len(original_rows)

    back_to_csv = tmp_path / "out.csv"
    report_b = convert(as_json, "json", "csv", back_to_csv)
    assert report_b.ok

    final_header, final_rows = _read_csv_rows(back_to_csv)
    assert final_header == original_header
    assert final_rows == original_rows

    payload = json.loads(as_json.read_text())
    assert list(payload[0].keys()) == original_header


@pytest.mark.parametrize("fmt", _FORMATS)
def test_every_format_round_trips_through_csv(fmt: str, clean_csv: Path, tmp_path: Path) -> None:
    """csv -> fmt -> csv preserves the rows for each supported format."""
    _, original_rows = _read_csv_rows(clean_csv)
    mid = tmp_path / f"mid.{fmt}"
    out = tmp_path / "out.csv"

    assert convert(clean_csv, "csv", fmt, mid).ok
    report = convert(mid, fmt, "csv", out)
    assert report.ok

    _, final_rows = _read_csv_rows(out)
    assert final_rows == original_rows


def test_messy_csv_produces_warnings_not_traceback(messy_csv: Path, tmp_path: Path) -> None:
    """A quirky CSV converts with a non-empty warnings list and still writes output."""
    report = convert(messy_csv, "csv", "json", tmp_path / "messy.json")
    assert report.ok is True
    assert report.warnings
    rows = json.loads((tmp_path / "messy.json").read_text())
    assert {"name", "role", "note"} <= set(rows[0])
    assert any("_extra_1" in row for row in rows)


def test_missing_input_returns_report_not_exception(tmp_path: Path) -> None:
    """A missing input path yields ok=False with a warning, never an exception."""
    report = convert(tmp_path / "nope.csv", "csv", "json", tmp_path / "out.json")
    assert report.ok is False
    assert report.rows == 0
    assert any("input not found" in warning for warning in report.warnings)


def test_unknown_pair_raises_conversion_error(clean_csv: Path, tmp_path: Path) -> None:
    """An unsupported (src, dst) pair is a usage error, not a warning."""
    with pytest.raises(ConversionError):
        convert(clean_csv, "csv", "sigma-json", tmp_path / "out.json")


def test_malformed_json_yields_warning(tmp_path: Path) -> None:
    """Broken JSON content becomes a warning; the converter does not raise."""
    broken = tmp_path / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")
    report = convert(broken, "json", "csv", tmp_path / "out.csv")
    assert report.rows == 0
    assert any("could not parse as json" in warning for warning in report.warnings)


def test_xml_shape_round_trips(clean_csv: Path, tmp_path: Path) -> None:
    """The XML writer emits the round-trippable <rows><row><col> shape."""
    xml_path = tmp_path / "mid.xml"
    assert convert(clean_csv, "csv", "xml", xml_path).ok
    text = xml_path.read_text()
    assert "<rows>" in text and '<col name="name">' in text
