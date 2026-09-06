"""Word rendering for advisory and executive_summary: headings, banner, provenance footer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_BANNER_DEFAULT = "OFFICIAL — DEMO"


def render_docx(artefact: Any, path: Path) -> None:
    """Render an advisory or executive summary to a .docx file at `path`."""
    from docx import Document

    document = Document()
    banner = artefact.confidence_notes.strip() or _BANNER_DEFAULT
    document.add_paragraph(banner).runs[0].bold = True
    document.add_heading(artefact.title, level=0)

    if str(artefact.artefact_type) == "advisory":
        _advisory_body(document, artefact)
    else:
        _executive_summary_body(document, artefact)

    section = document.sections[0]
    section.footer.paragraphs[0].text = f"Provenance: {path.name}.manifest.json"
    document.save(str(path))


def _executive_summary_body(document: Any, a: Any) -> None:
    """Fill a Word document with executive-summary content."""
    document.add_paragraph(a.headline).runs[0].italic = True
    document.add_paragraph(a.context)
    _bullet_section(document, "Key points", a.key_points)
    _bullet_section(document, "Implications", a.implications)
    _bullet_section(document, "Recommended actions", a.recommended_actions)
    document.add_heading("Takeaway", level=1)
    document.add_paragraph(a.one_line_takeaway)


def _advisory_body(document: Any, a: Any) -> None:
    """Fill a Word document with advisory content."""
    for label, value in (
        ("Advisory ID", a.advisory_id),
        ("Severity", a.severity.value),
        ("Issued for", a.issued_for),
    ):
        document.add_paragraph(f"{label}: {value}")
    document.add_heading("Summary", level=1)
    document.add_paragraph(a.summary)
    document.add_heading("Background", level=1)
    document.add_paragraph(a.background)
    document.add_heading("Technical details", level=1)
    for detail in a.technical_details:
        document.add_heading(detail.heading, level=2)
        document.add_paragraph(detail.body)
    _bullet_section(document, "Affected entities", a.affected_entities)
    document.add_heading("Indicators", level=1)
    for indicator in a.indicators:
        note = f" — {indicator.note}" if indicator.note else ""
        line = f"{indicator.ioc_type.value}: {indicator.value}{note}"
        document.add_paragraph(line, style="List Bullet")
    _bullet_section(
        document,
        "Recommended actions",
        [f"[{r.priority.value}] {r.action}" for r in a.recommended_actions],
    )
    _bullet_section(document, "References", a.references)
    document.add_paragraph(f"Handling: {a.handling_caveat}").runs[0].italic = True


def _bullet_section(document: Any, heading: str, items: list[Any]) -> None:
    """Add a level-1 heading and one bulleted paragraph per item."""
    document.add_heading(heading, level=1)
    for item in items:
        document.add_paragraph(str(item), style="List Bullet")
