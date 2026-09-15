"""Drawing helpers for the advisory PDF: header band, at-a-glance strip, section headings,
bordered indicator/action tables, and the handling callout -- all colour-driven by a `Theme`.

fpdf2's `Table` paints every *unfilled* cell using the `FPDF` instance's currently active
`fill_color`, not a true transparent background, so every table builder here resets it to
white first -- otherwise a colour left over from a rect drawn just above (a heading's accent
bar, a severity chip) bleeds into the table. Found by rendering and inspecting real output,
not by reading the fpdf2 source.
"""

from __future__ import annotations

from typing import Any

from rupantar.render.context import RenderContext
from rupantar.render.theme import Theme

_PAGE_WHITE = (255, 255, 255)


def latin1(text: str) -> str:
    """Coerce text into the latin-1 range fpdf2's core fonts can render."""
    swaps = {"—": "-", "–": "-", "‘": "'", "’": "'", "“": '"', "”": '"'}
    for src, dst in swaps.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")


def warn(context: RenderContext | None, message: str) -> None:
    """Record a degradation warning on the shared context, if one was given."""
    if context is not None:
        context.warnings.append(message)


def header_band(pdf: Any, theme: Theme, title: str, banner: str) -> None:
    """A coloured band across the top of the first page: classification banner + title."""
    band_h = 30
    pdf.set_fill_color(*theme.rgb("primary"))
    pdf.rect(0, 0, pdf.w, band_h, style="F")
    pdf.set_text_color(*theme.rgb("text"))
    pdf.set_xy(pdf.l_margin, 6)
    pdf.set_font("Helvetica", style="B", size=9)
    pdf.cell(pdf.epw, 5, latin1(banner))
    pdf.set_xy(pdf.l_margin, 13)
    pdf.set_font("Helvetica", style="B", size=17)
    fitted = latin1(title)
    while pdf.get_string_width(fitted) > pdf.epw and len(fitted) > 10:
        fitted = fitted[:-4] + "..."
    pdf.cell(pdf.epw, 10, fitted)
    pdf.set_y(band_h + 6)
    pdf.set_text_color(0, 0, 0)


def at_a_glance(pdf: Any, theme: Theme, advisory_id: str, severity: str, issued_for: str) -> None:
    """The severity badge plus advisory id / issued-for line, just under the header band."""
    y = pdf.get_y()
    pdf.set_font("Helvetica", style="B", size=10)
    chip_w = pdf.get_string_width(severity.upper()) + 10
    pdf.set_fill_color(*theme.severity_rgb(severity))
    pdf.rect(pdf.l_margin, y, chip_w, 8, style="F", round_corners=True, corner_radius=1.5)
    pdf.set_text_color(*theme.rgb_on(theme.severity_colour(severity)))
    pdf.set_xy(pdf.l_margin, y)
    pdf.cell(chip_w, 8, severity.upper(), align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", size=10)
    pdf.set_xy(pdf.l_margin + chip_w + 4, y)
    pdf.cell(0, 8, latin1(f"{advisory_id}  |  Issued for: {issued_for}"))
    pdf.ln(14)


def heading(pdf: Any, theme: Theme, text: str) -> None:
    """A section heading with a coloured left accent bar."""
    x, y = pdf.l_margin, pdf.get_y()
    pdf.set_fill_color(*theme.rgb("accent"))
    pdf.rect(x, y + 1, 2.2, 6, style="F")
    pdf.set_xy(x + 5, y)
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.set_text_color(*theme.rgb("primary"))
    pdf.cell(0, 8, latin1(text))
    pdf.ln(9)
    pdf.set_text_color(0, 0, 0)


def subheading(pdf: Any, text: str) -> None:
    """A bold sub-heading line with no accent bar, for nested technical-detail titles."""
    pdf.set_font("Helvetica", style="B", size=10)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, 5.2, latin1(text), wrapmode="WORD")


def body(pdf: Any, text: str) -> None:
    """A wrapped body paragraph in the default black text colour."""
    pdf.set_font("Helvetica", size=10)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, 5.2, latin1(text), wrapmode="WORD")
    pdf.ln(2)


def callout(pdf: Any, theme: Theme, text: str) -> None:
    """A tinted, bordered callout box (surface fill, on-dark text) for a handling caveat."""
    pdf.set_font("Helvetica", style="I", size=9)
    lines = pdf.multi_cell(
        pdf.epw - 6, 5, latin1(text), wrapmode="WORD", dry_run=True, output="LINES"
    )
    box_y = pdf.get_y()
    box_h = len(lines) * 5 + 6
    pdf.set_fill_color(*theme.rgb("surface"))
    pdf.rect(pdf.l_margin, box_y, pdf.epw, box_h, style="F")
    pdf.set_xy(pdf.l_margin + 3, box_y + 3)
    pdf.set_text_color(*theme.rgb("text"))
    pdf.multi_cell(pdf.epw - 6, 5, latin1(text), wrapmode="WORD")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def footer(pdf: Any, theme: Theme) -> None:
    """Page number plus a thin accent rule, drawn on every page via `FPDF.footer()`."""
    pdf.set_draw_color(*theme.rgb("accent"))
    pdf.set_line_width(0.6)
    pdf.line(pdf.l_margin, pdf.h - 18, pdf.w - pdf.r_margin, pdf.h - 18)
    pdf.set_y(-15)
    pdf.set_font("Helvetica", size=8)
    pdf.set_text_color(*theme.rgb("text_muted"))
    pdf.cell(0, 10, latin1(f"Page {pdf.page_no()}"), align="C")


def indicators_table(
    pdf: Any, theme: Theme, font_face: Any, indicators: list[Any], context: RenderContext | None
) -> None:
    """A bordered Type/Value/Note table with a shaded header row; degrades to bullets on error."""
    if not indicators:
        body(pdf, "none provided")
        return
    try:
        pdf.set_fill_color(*_PAGE_WHITE)
        with pdf.table(
            col_widths=(2, 5, 3),
            headings_style=font_face(emphasis="B", color=255, fill_color=theme.rgb("primary")),
            text_align="LEFT",
        ) as table:
            header_row = table.row()
            for label in ("Type", "Value", "Note"):
                header_row.cell(label)
            for indicator in indicators:
                row = table.row()
                row.cell(indicator.ioc_type.value)
                row.cell(indicator.value)
                row.cell(indicator.note or "-")
    except Exception as exc:  # a structurally odd table must never fail the whole document
        warn(context, f"indicators table could not be built ({exc}); using a bulleted list")
        for indicator in indicators:
            note = f" - {indicator.note}" if indicator.note else ""
            body(pdf, f"- {indicator.ioc_type.value}: {indicator.value}{note}")


def actions_table(
    pdf: Any, theme: Theme, font_face: Any, actions: list[Any], context: RenderContext | None
) -> None:
    """A bordered Priority/Action table, the priority cell colour-coded; degrades to bullets."""
    if not actions:
        body(pdf, "none")
        return
    try:
        pdf.set_fill_color(*_PAGE_WHITE)
        with pdf.table(col_widths=(2, 6), text_align="LEFT") as table:
            header_row = table.row()
            header_row.cell("Priority")
            header_row.cell("Action")
            for action in actions:
                priority = action.priority.value
                priority_hex = theme.severity_colour(priority)
                row = table.row()
                row.cell(
                    priority.upper(),
                    style=font_face(
                        fill_color=theme.severity_rgb(priority),
                        color=theme.rgb_on(priority_hex),
                    ),
                )
                row.cell(action.action)
    except Exception as exc:
        warn(context, f"actions table could not be built ({exc}); using a bulleted list")
        for action in actions:
            body(pdf, f"- [{action.priority.value}] {action.action}")
