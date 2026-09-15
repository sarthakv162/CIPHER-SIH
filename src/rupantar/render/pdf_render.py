"""Advisory PDF rendering with fpdf2 and the theme design system: a coloured header band,
a severity badge, accent-barred section headings, real bordered tables for indicators and
recommended actions, and a tinted handling callout. Core fonts are latin-1, so text is
transliterated. Never raises: a broken theme degrades to a hardcoded fallback palette, and a
table-build problem degrades to the previous plain-bulleted rendering -- both record a warning
on `context` instead of failing the document.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rupantar.render import _pdf_layout as layout
from rupantar.render._theme_fallback import safe_theme
from rupantar.render.context import RenderContext


def render_pdf(artefact: Any, path: Path, *, context: RenderContext | None = None) -> None:
    """Render an advisory to a PDF file at `path`."""
    from fpdf import FPDF
    from fpdf.fonts import FontFace

    theme = safe_theme(context)

    class _ThemedPDF(FPDF):  # local: keeps the fpdf import lazy (INV-3)
        def footer(self) -> None:
            layout.footer(self, theme)

    pdf = _ThemedPDF()
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.add_page()

    banner = artefact.confidence_notes.strip() or "OFFICIAL - DEMO"
    layout.header_band(pdf, theme, artefact.title, banner)
    layout.at_a_glance(
        pdf, theme, artefact.advisory_id, artefact.severity.value, artefact.issued_for
    )

    layout.heading(pdf, theme, "Summary")
    layout.body(pdf, artefact.summary)
    layout.heading(pdf, theme, "Background")
    layout.body(pdf, artefact.background)
    layout.heading(pdf, theme, "Technical details")
    for detail in artefact.technical_details:
        layout.subheading(pdf, detail.heading)
        layout.body(pdf, detail.body)

    layout.heading(pdf, theme, "Affected entities")
    layout.body(pdf, "; ".join(artefact.affected_entities) or "none stated")

    layout.heading(pdf, theme, "Indicators")
    layout.indicators_table(pdf, theme, FontFace, artefact.indicators, context)

    layout.heading(pdf, theme, "Recommended actions")
    layout.actions_table(pdf, theme, FontFace, artefact.recommended_actions, context)

    layout.heading(pdf, theme, "References")
    layout.body(pdf, "\n".join(f"- {r}" for r in artefact.references) or "none")

    layout.heading(pdf, theme, "Handling")
    layout.callout(pdf, theme, artefact.handling_caveat)

    pdf.output(str(path))
