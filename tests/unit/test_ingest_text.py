"""Text extraction: every supported type yields blocks; bad input yields a warning, not a raise."""

from __future__ import annotations

from pathlib import Path

import pytest

from rupantar.ingest.text import extract_blocks, extract_text

_INGEST = Path(__file__).resolve().parents[1] / "fixtures" / "ingest"


@pytest.mark.parametrize(
    "name",
    ["advisory.pdf", "sample.docx", "sample.html", "sample.md", "sample.txt", "multipage.pdf"],
)
def test_supported_types_extract_nonempty_blocks(name: str) -> None:
    blocks, warnings = extract_blocks(_INGEST / name)
    assert blocks and all(b.text.strip() for b in blocks)
    assert warnings == []


def test_multipage_pdf_keeps_page_numbers_and_a_heading() -> None:
    blocks, warnings = extract_blocks(_INGEST / "multipage.pdf")
    assert warnings == []
    assert [b.page for b in blocks] == [1, 2]
    assert all(b.source_name == "multipage.pdf" for b in blocks)
    assert blocks[1].heading == "Evidence And Provenance"


def test_html_script_and_style_content_is_stripped() -> None:
    (block,) = extract_blocks(_INGEST / "sample.html")[0]
    assert "SCRIPT_SHOULD_BE_STRIPPED" not in block.text
    assert "INLINE_SCRIPT_ALSO_STRIPPED" not in block.text
    assert "secret-styling-token" not in block.text
    assert "bada55" not in block.text
    assert "Air-gapped deployments" in block.text


def test_unknown_suffix_warns_without_raising(tmp_path: Path) -> None:
    odd = tmp_path / "notes.rtf"
    odd.write_text("hello", encoding="utf-8")
    blocks, warnings = extract_blocks(odd)
    assert blocks == []
    assert warnings and "unsupported text type" in warnings[0]


def test_garbage_pdf_warns_without_raising(tmp_path: Path) -> None:
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.4 this is not really a pdf \x00\x01\x02")
    blocks, warnings = extract_blocks(broken)
    assert blocks == []
    assert warnings and "broken.pdf" in warnings[0]
    assert "Traceback" not in warnings[0]


def test_empty_plain_file_warns(tmp_path: Path) -> None:
    empty = tmp_path / "empty.txt"
    empty.write_text("   \n", encoding="utf-8")
    blocks, warnings = extract_blocks(empty)
    assert blocks == []
    assert warnings


def test_extract_text_shim_joins_blocks() -> None:
    text, warnings = extract_text(_INGEST / "multipage.pdf")
    assert warnings == []
    assert "Offline Content Engines" in text and "Evidence And Provenance" in text
