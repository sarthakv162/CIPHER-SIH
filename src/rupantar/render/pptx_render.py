"""PowerPoint rendering for a Presentation artefact: title slide plus one slide per Slide.

After saving, `_repair_ooxml` patches `ppt/presentation.xml`: python-pptx never writes the
`<p:notesMasterIdLst>` element even when it adds a notes master, which Keynote's strict
importer rejects outright ("file format is invalid"). It also drops the deprecated
`<p:sldSz type=...>` attribute. PowerPoint / LibreOffice tolerate both; Keynote does not.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Any

# Content slides never use layout 0 (the Title Slide layout) — the deck already has one.
_LAYOUT_INDEX = {"title": 2, "bullets": 1, "two_column": 3, "quote": 1, "closing": 2}
_NOTES_MASTER_RID = re.compile(
    r'<Relationship\b(?=[^>]*\bType="[^"]*/notesMaster")[^>]*\bId="(rId\d+)"'
)
_SLD_SZ_TYPE = re.compile(r'(<p:sldSz\b[^>]*?)\s+type="[^"]*"([^>]*/>)')


def render_pptx(artefact: Any, path: Path) -> None:
    """Render the deck to a .pptx file; speaker notes go in each slide's notes pane."""
    from pptx import Presentation as PptxPresentation

    deck = PptxPresentation()
    _title_slide(deck, artefact.title, artefact.deck_summary)
    for slide in artefact.slides:
        _content_slide(deck, slide)
    deck.save(str(path))
    _repair_ooxml(path)


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


def _repair_ooxml(path: Path) -> None:
    """Rewrite the package with `ppt/presentation.xml` made acceptable to strict importers."""
    with zipfile.ZipFile(path) as archive:
        parts = [(info, archive.read(info.filename)) for info in archive.infolist()]
    rels = next(d for i, d in parts if i.filename == "ppt/_rels/presentation.xml.rels")
    match = _NOTES_MASTER_RID.search(rels.decode("utf-8"))
    notes_rid = match.group(1) if match else None

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as out:
        for info, data in parts:
            if info.filename == "ppt/presentation.xml":
                data = _patch_presentation(data.decode("utf-8"), notes_rid).encode("utf-8")
            out.writestr(info, data)
    path.write_bytes(buffer.getvalue())


def _patch_presentation(xml: str, notes_rid: str | None) -> str:
    """Add `<p:notesMasterIdLst>` after the slide-master list and drop `<p:sldSz type=...>`."""
    xml = _SLD_SZ_TYPE.sub(r"\1\2", xml)
    if notes_rid and "notesMasterIdLst" not in xml:
        xml = xml.replace(
            "</p:sldMasterIdLst>",
            "</p:sldMasterIdLst>"
            f'<p:notesMasterIdLst><p:notesMasterId r:id="{notes_rid}"/></p:notesMasterIdLst>',
            1,
        )
    return xml
