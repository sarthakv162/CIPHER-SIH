"""Advisory PDF rendering with fpdf2. Core fonts are latin-1, so text is transliterated."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _latin1(text: str) -> str:
    """Coerce text into the latin-1 range fpdf2's core fonts can render."""
    swaps = {"—": "-", "–": "-", "‘": "'", "’": "'", "“": '"', "”": '"'}
    for src, dst in swaps.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")


def render_pdf(artefact: Any, path: Path) -> None:
    """Render an advisory to a PDF file at `path`."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    banner = artefact.confidence_notes.strip() or "OFFICIAL - DEMO"
    _line(pdf, _latin1(banner), size=10, style="B")
    _line(pdf, _latin1(artefact.title), size=16, style="B")
    for label, value in (
        ("Advisory ID", artefact.advisory_id),
        ("Severity", artefact.severity.value),
        ("Issued for", artefact.issued_for),
    ):
        _line(pdf, _latin1(f"{label}: {value}"), size=10)

    _section(pdf, "Summary", artefact.summary)
    _section(pdf, "Background", artefact.background)
    for detail in artefact.technical_details:
        _section(pdf, detail.heading, detail.body)
    _section(pdf, "Affected entities", "; ".join(artefact.affected_entities) or "none stated")
    indicators = "\n".join(
        f"- {i.ioc_type.value}: {i.value}" + (f" ({i.note})" if i.note else "")
        for i in artefact.indicators
    )
    _section(pdf, "Indicators", indicators or "none provided")
    actions = "\n".join(f"- [{r.priority.value}] {r.action}" for r in artefact.recommended_actions)
    _section(pdf, "Recommended actions", actions)
    _section(pdf, "References", "\n".join(f"- {r}" for r in artefact.references) or "none")
    _section(pdf, "Handling", artefact.handling_caveat)

    pdf.output(str(path))


def _line(pdf: Any, text: str, *, size: int, style: str = "") -> None:
    """Write one wrapped paragraph at the given font size and style."""
    pdf.set_font("Helvetica", style=style, size=size)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, size * 0.6, text, new_x="LMARGIN", new_y="NEXT", wrapmode="CHAR")


def _section(pdf: Any, heading: str, body: str) -> None:
    """Write a bold heading followed by a body paragraph."""
    pdf.ln(2)
    _line(pdf, _latin1(heading), size=12, style="B")
    _line(pdf, _latin1(body), size=10)
