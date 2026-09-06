"""Phase 4 verify: every artefact fixture renders to its formats and the binaries open."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from rupantar.core.artefacts import ARTEFACT_MODELS
from rupantar.render.base import FORMATS, render

_TYPES = sorted(ARTEFACT_MODELS)


def _load(artefact_type: str, artefacts_dir: Path):  # type: ignore[no-untyped-def]
    model = ARTEFACT_MODELS[artefact_type]
    return model.model_validate_json((artefacts_dir / f"{artefact_type}.json").read_text())


@pytest.mark.parametrize("artefact_type", _TYPES)
def test_all_declared_formats_are_written(
    artefact_type: str, artefacts_dir: Path, tmp_path: Path
) -> None:
    """render() produces one non-empty file per format in FORMATS."""
    artefact = _load(artefact_type, artefacts_dir)
    paths = render(artefact, tmp_path)
    suffixes = {p.suffix.lstrip(".") for p in paths}
    assert suffixes == set(FORMATS[artefact_type])
    for path in paths:
        assert path.is_file() and path.stat().st_size > 0


def test_advisory_binaries_open(artefacts_dir: Path, tmp_path: Path) -> None:
    """The advisory docx and pdf open and carry its indicators and actions."""
    import docx

    advisory = _load("advisory", artefacts_dir)
    render(advisory, tmp_path)

    document = docx.Document(str(tmp_path / "advisory.docx"))
    text = "\n".join(p.text for p in document.paragraphs)
    assert advisory.indicators[0].value in text
    assert advisory.recommended_actions[0].action in text

    pdf = (tmp_path / "advisory.pdf").read_bytes()
    assert pdf.startswith(b"%PDF") and pdf.rstrip().endswith(b"%%EOF")


def test_executive_summary_docx_opens(artefacts_dir: Path, tmp_path: Path) -> None:
    """The executive summary docx opens through python-docx."""
    import docx

    artefact = _load("executive_summary", artefacts_dir)
    render(artefact, tmp_path)
    document = docx.Document(str(tmp_path / "executive_summary.docx"))
    assert artefact.title in "\n".join(p.text for p in document.paragraphs)


def test_presentation_pptx_slides_and_notes(artefacts_dir: Path, tmp_path: Path) -> None:
    """The pptx has slides + 1 and notes text is present."""
    import pptx

    deck = _load("presentation", artefacts_dir)
    render(deck, tmp_path)
    opened = pptx.Presentation(str(tmp_path / "presentation.pptx"))
    assert len(opened.slides) == len(deck.slides) + 1
    notes = " ".join(
        s.notes_slide.notes_text_frame.text for s in opened.slides if s.has_notes_slide
    )
    assert deck.slides[0].speaker_notes in notes


def test_infographic_svg_is_xml(artefacts_dir: Path, tmp_path: Path) -> None:
    """The infographic SVG parses as XML with an <svg> root."""
    spec = _load("infographic_spec", artefacts_dir)
    render(spec, tmp_path)
    root = ET.fromstring((tmp_path / "infographic_spec.svg").read_text(encoding="utf-8"))
    assert root.tag.endswith("svg")


def test_video_package_srt_has_cues(artefacts_dir: Path, tmp_path: Path) -> None:
    """The video package SRT has one cue per scene."""
    video = _load("video_package", artefacts_dir)
    render(video, tmp_path)
    srt = (tmp_path / "video_package.srt").read_text(encoding="utf-8")
    assert "-->" in srt
    assert srt.count("-->") == len(video.scenes)
