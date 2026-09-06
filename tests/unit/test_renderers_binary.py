"""Binary renderers: docx, pptx, pdf, and svg outputs open without corruption."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from rupantar.core.artefacts import Advisory, ExecutiveSummary, InfographicSpec, Presentation
from rupantar.render.docx_render import render_docx
from rupantar.render.pdf_render import render_pdf
from rupantar.render.pptx_render import render_pptx
from rupantar.render.svg_render import render_svg


def _load(model: type, artefacts_dir: Path, name: str):  # type: ignore[no-untyped-def]
    return model.model_validate_json((artefacts_dir / f"{name}.json").read_text())


def test_docx_advisory_and_exec_summary_open(artefacts_dir: Path, tmp_path: Path) -> None:
    """Both docx-capable artefacts round-trip through python-docx."""
    import docx

    advisory = _load(Advisory, artefacts_dir, "advisory")
    exec_summary = _load(ExecutiveSummary, artefacts_dir, "executive_summary")
    for artefact, name in ((advisory, "advisory"), (exec_summary, "executive_summary")):
        path = tmp_path / f"{name}.docx"
        render_docx(artefact, path)
        text = "\n".join(p.text for p in docx.Document(str(path)).paragraphs)
        assert artefact.title in text


def test_pptx_slide_count_and_notes(artefacts_dir: Path, tmp_path: Path) -> None:
    """The deck has one slide per Slide plus a title slide, and carries speaker notes."""
    import pptx

    deck = _load(Presentation, artefacts_dir, "presentation")
    path = tmp_path / "presentation.pptx"
    render_pptx(deck, path)
    opened = pptx.Presentation(str(path))
    assert len(opened.slides) == len(deck.slides) + 1
    notes = [s.notes_slide.notes_text_frame.text for s in opened.slides if s.has_notes_slide]
    assert any(deck.slides[0].speaker_notes in n for n in notes)


def test_pdf_advisory_is_well_formed(artefacts_dir: Path, tmp_path: Path) -> None:
    """The advisory PDF starts with %PDF and ends with %%EOF."""
    advisory = _load(Advisory, artefacts_dir, "advisory")
    path = tmp_path / "advisory.pdf"
    render_pdf(advisory, path)
    raw = path.read_bytes()
    assert raw.startswith(b"%PDF")
    assert raw.rstrip().endswith(b"%%EOF")


def test_svg_infographic_parses_as_xml(artefacts_dir: Path, tmp_path: Path) -> None:
    """The infographic SVG parses and its root element is <svg>."""
    spec = _load(InfographicSpec, artefacts_dir, "infographic_spec")
    path = tmp_path / "infographic_spec.svg"
    render_svg(spec, path)
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    assert root.tag.endswith("svg")
    assert spec.sections[0].stat_value in path.read_text(encoding="utf-8")
