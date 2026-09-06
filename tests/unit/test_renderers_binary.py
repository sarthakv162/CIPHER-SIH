"""Binary renderers: docx, pptx, pdf, svg — opened and inspected, not just size-checked."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from rupantar.core.artefacts import Advisory, ExecutiveSummary, InfographicSpec, Presentation
from rupantar.render.docx_render import render_docx
from rupantar.render.pdf_render import render_pdf
from rupantar.render.pptx_render import _body_placeholder, render_pptx
from rupantar.render.svg_render import render_svg


def _load(model: type, artefacts_dir: Path, name: str):  # type: ignore[no-untyped-def]
    return model.model_validate_json((artefacts_dir / f"{name}.json").read_text())


def _headings(document: object) -> set[str]:
    """Every paragraph styled as a heading or title in a python-docx document."""
    return {
        p.text
        for p in document.paragraphs  # type: ignore[attr-defined]
        if p.style.name.startswith(("Heading", "Title"))
    }


def test_docx_advisory_carries_its_content(artefacts_dir: Path, tmp_path: Path) -> None:
    """The advisory .docx opens and contains its title, headings, indicators, and actions."""
    import docx

    advisory = _load(Advisory, artefacts_dir, "advisory")
    path = tmp_path / "advisory.docx"
    render_docx(advisory, path)

    document = docx.Document(str(path))
    text = "\n".join(p.text for p in document.paragraphs)
    footer = document.sections[0].footer.paragraphs[0].text

    assert advisory.title in text
    assert {"Summary", "Background", "Technical details", "Indicators"} <= _headings(document)
    assert advisory.indicators[0].value in text
    assert advisory.recommended_actions[0].action in text
    assert footer == f"Provenance: {path.name}.manifest.json"


def test_docx_executive_summary_opens_with_headings(artefacts_dir: Path, tmp_path: Path) -> None:
    """The executive-summary .docx opens and carries its section headings."""
    import docx

    summary = _load(ExecutiveSummary, artefacts_dir, "executive_summary")
    path = tmp_path / "executive_summary.docx"
    render_docx(summary, path)

    document = docx.Document(str(path))
    text = "\n".join(p.text for p in document.paragraphs)
    assert summary.title in text
    assert {"Key points", "Implications", "Takeaway"} <= _headings(document)


def test_pptx_structure_matches_the_deck(artefacts_dir: Path, tmp_path: Path) -> None:
    """Open with python-pptx: one content slide per Slide + a title slide, each with a title,
    at least one bullet, and speaker notes; the package metadata matches the slide count."""
    import pptx

    deck = _load(Presentation, artefacts_dir, "presentation")
    path = tmp_path / "presentation.pptx"
    render_pptx(deck, path)

    opened = pptx.Presentation(str(path))
    slides = list(opened.slides)
    assert len(slides) == len(deck.slides) + 1  # + the opening title slide

    for slide_no, (rendered, spec) in enumerate(zip(slides[1:], deck.slides, strict=True)):
        where = f"content slide {slide_no}"
        assert rendered.shapes.title is not None, f"{where}: no title placeholder"
        assert rendered.shapes.title.text == spec.title, f"{where}: wrong title"
        body = _body_placeholder(rendered)
        assert body is not None and body.has_text_frame, f"{where}: no body placeholder"
        bullets = [p.text for p in body.text_frame.paragraphs if p.text.strip()]
        assert len(bullets) >= 1, f"{where}: no bullets"
        assert rendered.has_notes_slide, f"{where}: no notes slide"
        assert rendered.notes_slide.notes_text_frame.text.strip() == spec.speaker_notes.strip()

    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        app_xml = archive.read("docProps/app.xml").decode("utf-8")
    assert re.search(r"<Slides>(\d+)</Slides>", app_xml).group(1) == str(len(opened.slides))
    assert not any("thumbnail" in n or "printerSettings" in n for n in names)


def test_pptx_layouts_never_use_the_title_slide_layout(artefacts_dir: Path, tmp_path: Path) -> None:
    """A content slide with layout 'title' must not land on the Title Slide layout."""
    import pptx

    deck = _load(Presentation, artefacts_dir, "presentation")
    path = tmp_path / "presentation.pptx"
    render_pptx(deck, path)
    opened = pptx.Presentation(str(path))
    title_layout = opened.slide_masters[0].slide_layouts[0]
    for rendered in list(opened.slides)[1:]:
        assert rendered.slide_layout != title_layout


def test_pdf_advisory_opens_and_has_text(artefacts_dir: Path, tmp_path: Path) -> None:
    """The advisory PDF parses with pypdf, has a page, and its text carries the title."""
    from pypdf import PdfReader

    advisory = _load(Advisory, artefacts_dir, "advisory")
    path = tmp_path / "advisory.pdf"
    render_pdf(advisory, path)

    raw = path.read_bytes()
    assert raw.startswith(b"%PDF-") and raw.rstrip().endswith(b"%%EOF")

    reader = PdfReader(str(path))
    assert len(reader.pages) >= 1
    text = "".join(page.extract_text() for page in reader.pages)
    assert "Summary" in text
    assert advisory.advisory_id in text


def test_svg_infographic_parses_and_carries_a_stat(artefacts_dir: Path, tmp_path: Path) -> None:
    """The infographic SVG parses as XML with an <svg> root and shows a stat value."""
    spec = _load(InfographicSpec, artefacts_dir, "infographic_spec")
    path = tmp_path / "infographic_spec.svg"
    render_svg(spec, path)
    body = path.read_text(encoding="utf-8")
    assert ET.fromstring(body).tag.endswith("svg")
    assert spec.sections[0].stat_value in body
