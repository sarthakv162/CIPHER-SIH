"""PowerPoint rendering for a Presentation artefact: title slide plus one slide per Slide."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_LAYOUT_INDEX = {"title": 0, "bullets": 1, "two_column": 3, "quote": 1, "closing": 1}


def render_pptx(artefact: Any, path: Path) -> None:
    """Render the deck to a .pptx file; speaker notes go in each slide's notes pane."""
    from pptx import Presentation as PptxPresentation

    deck = PptxPresentation()
    _title_slide(deck, artefact.title, artefact.deck_summary)
    for slide in artefact.slides:
        _content_slide(deck, slide)
    deck.save(str(path))


def _title_slide(deck: Any, title: str, subtitle: str) -> None:
    """Add the opening title slide."""
    slide = deck.slides.add_slide(deck.slide_layouts[0])
    slide.shapes.title.text = title
    body = _body_placeholder(slide)
    if body is not None:
        body.text = subtitle


def _content_slide(deck: Any, slide_spec: Any) -> None:
    """Add one content slide with bullets and speaker notes."""
    layout_index = _LAYOUT_INDEX.get(slide_spec.layout.value, 1)
    slide = deck.slides.add_slide(deck.slide_layouts[layout_index])
    if slide.shapes.title is not None:
        slide.shapes.title.text = slide_spec.title
    body = _body_placeholder(slide)
    if body is not None and slide_spec.bullets:
        frame = body.text_frame
        frame.text = str(slide_spec.bullets[0])
        for bullet in slide_spec.bullets[1:]:
            frame.add_paragraph().text = str(bullet)
    slide.notes_slide.notes_text_frame.text = slide_spec.speaker_notes


def _body_placeholder(slide: Any) -> Any:
    """Return the first non-title placeholder on a slide, or None."""
    for placeholder in slide.placeholders:
        if placeholder.placeholder_format.idx != 0:
            return placeholder
    return None
