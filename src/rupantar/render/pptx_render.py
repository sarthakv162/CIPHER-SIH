"""PowerPoint rendering for a Presentation artefact: title slide plus one slide per Slide.

After saving, `_repair_ooxml` strips non-portable parts and corrects `docProps/app.xml` so
strict importers (Keynote) accept the file — python-pptx leaves app.xml claiming zero slides.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

# Content slides never use layout 0 (the Title Slide layout) — the deck already has one.
_LAYOUT_INDEX = {"title": 2, "bullets": 1, "two_column": 3, "quote": 1, "closing": 2}
_STRIP_PARTS = ("ppt/printerSettings/printerSettings1.bin", "docProps/thumbnail.jpeg")


def render_pptx(artefact: Any, path: Path) -> None:
    """Render the deck to a .pptx file; speaker notes go in each slide's notes pane."""
    from pptx import Presentation as PptxPresentation

    deck = PptxPresentation()
    _title_slide(deck, artefact.title, artefact.deck_summary)
    for slide in artefact.slides:
        _content_slide(deck, slide)
    deck.save(str(path))
    _repair_ooxml(path, [artefact.title, *(s.title for s in artefact.slides)], len(artefact.slides))


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


def _repair_ooxml(path: Path, titles: list[str], notes_count: int) -> None:
    """Rewrite the package without the non-portable parts and with a correct app.xml."""
    with zipfile.ZipFile(path) as archive:
        parts = [(info, archive.read(info.filename)) for info in archive.infolist()]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as out:
        for info, data in parts:
            if info.filename in _STRIP_PARTS:
                continue
            out.writestr(info, _patch_part(info.filename, data, titles, notes_count))
    path.write_bytes(buffer.getvalue())


def _patch_part(name: str, data: bytes, titles: list[str], notes_count: int) -> bytes:
    """Return `data` with the thumbnail/printer references removed and app.xml corrected."""
    if name == "[Content_Types].xml":
        text = data.decode("utf-8")
        for fragment in (
            '<Default Extension="jpeg" ContentType="image/jpeg"/>',
            '<Default Extension="bin" ContentType="application/vnd.openxmlformats'
            '-officedocument.presentationml.printerSettings"/>',
        ):
            text = text.replace(fragment, "")
        return text.encode("utf-8")
    if name in ("_rels/.rels", "ppt/_rels/presentation.xml.rels"):
        needle = "thumbnail" if name == "_rels/.rels" else "printerSettings"
        return re.sub(rf"<Relationship [^>]*{needle}[^>]*/>", "", data.decode("utf-8")).encode(
            "utf-8"
        )
    if name == "docProps/app.xml":
        return _app_xml(data.decode("utf-8"), titles, notes_count).encode("utf-8")
    return data


def _app_xml(text: str, titles: list[str], notes_count: int) -> str:
    """Patch the extended-properties part so Slides/Notes/TitlesOfParts match reality."""
    lpstrs = "".join(f"<vt:lpstr>{escape(title)}</vt:lpstr>" for title in titles)
    return (
        text.replace("<Slides>0</Slides>", f"<Slides>{len(titles)}</Slides>")
        .replace("<Notes>0</Notes>", f"<Notes>{notes_count}</Notes>")
        .replace(
            '<vt:vector size="1" baseType="lpstr"><vt:lpstr>Office Theme</vt:lpstr></vt:vector>',
            f'<vt:vector size="{len(titles) + 1}" baseType="lpstr">'
            f"<vt:lpstr>Office Theme</vt:lpstr>{lpstrs}</vt:vector>",
        )
        .replace(
            "<vt:lpstr>Slide Titles</vt:lpstr></vt:variant><vt:variant><vt:i4>0</vt:i4>",
            "<vt:lpstr>Slide Titles</vt:lpstr></vt:variant>"
            f"<vt:variant><vt:i4>{len(titles)}</vt:i4>",
        )
    )
