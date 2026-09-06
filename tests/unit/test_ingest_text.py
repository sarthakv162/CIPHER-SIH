"""Text extraction: every supported type yields text; bad input yields a warning, not a raise."""

from __future__ import annotations

from pathlib import Path

import pytest

from rupantar.ingest.text import extract_text, text_block

_INGEST = Path(__file__).resolve().parents[1] / "fixtures" / "ingest"


@pytest.mark.parametrize(
    "name",
    ["advisory.pdf", "sample.docx", "sample.html", "sample.md", "sample.txt"],
)
def test_supported_types_extract_nonempty_text(name: str) -> None:
    text, warnings = extract_text(_INGEST / name)
    assert text.strip()
    assert warnings == []


def test_html_script_and_style_content_is_stripped() -> None:
    text, _ = extract_text(_INGEST / "sample.html")
    assert "SCRIPT_SHOULD_BE_STRIPPED" not in text
    assert "INLINE_SCRIPT_ALSO_STRIPPED" not in text
    assert "secret-styling-token" not in text
    assert "bada55" not in text
    assert "Air-gapped deployments" in text


def test_unknown_suffix_warns_without_raising(tmp_path: Path) -> None:
    odd = tmp_path / "notes.rtf"
    odd.write_text("hello", encoding="utf-8")
    text, warnings = extract_text(odd)
    assert text == ""
    assert warnings and "unsupported text type" in warnings[0]


def test_garbage_pdf_warns_without_raising(tmp_path: Path) -> None:
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.4 this is not really a pdf \x00\x01\x02")
    text, warnings = extract_text(broken)
    assert text == ""
    assert warnings and "broken.pdf" in warnings[0]
    assert "Traceback" not in warnings[0]


def test_text_block_wraps_and_reports_empty(tmp_path: Path) -> None:
    block, warnings = text_block(_INGEST / "sample.md")
    assert block is not None
    assert block.source_name == "sample.md"

    empty = tmp_path / "empty.txt"
    empty.write_text("   \n", encoding="utf-8")
    none_block, warns = text_block(empty)
    assert none_block is None
    assert warns
