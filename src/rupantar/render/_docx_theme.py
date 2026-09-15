"""Colour/shading decoration layer for the docx renderer: run colouring, paragraph/cell
shading and a divider rule via raw OXML (python-docx exposes none of these at the high
level), and the three genuinely tabular sections (at-a-glance, indicators, recommended
actions). Additive decoration on top of whatever template/style the caller already resolved.
"""

from __future__ import annotations

from typing import Any

from rupantar.render.theme import Theme, hex_to_rgb


def set_run_colour(paragraph: Any, hex_colour: str) -> None:
    """Tint every run of a paragraph with an RGB colour built from `#rrggbb`."""
    from docx.shared import RGBColor

    rgb = hex_to_rgb(hex_colour)
    for run in paragraph.runs:
        run.font.color.rgb = RGBColor(*rgb)


def shade_paragraph(paragraph: Any, hex_colour: str) -> None:
    """Set a paragraph's background shading via a raw `w:shd` element on its `pPr`."""
    _apply_shd(paragraph._p.get_or_add_pPr(), hex_colour)


def shade_cell(cell: Any, hex_colour: str) -> None:
    """Set a table cell's background shading via a raw `w:shd` element on its `tcPr`."""
    _apply_shd(cell._tc.get_or_add_tcPr(), hex_colour)


def bottom_border(paragraph: Any, hex_colour: str) -> None:
    """Add a coloured bottom-border rule under a paragraph, as a section divider."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    pPr = paragraph._p.get_or_add_pPr()
    border = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "18")
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), hex_colour.lstrip("#"))
    border.append(bottom)
    pPr.append(border)


def _apply_shd(element: Any, hex_colour: str) -> None:
    """Append a `w:shd` solid-fill child to a `pPr`/`tcPr` element."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_colour.lstrip("#"))
    element.append(shd)


def _set_column_widths(table: Any, inches: tuple[float, ...]) -> None:
    """Fix each column's width (in inches); Word's default auto-fit gives a long hash no room."""
    from docx.shared import Inches

    table.autofit = False
    for column, width in zip(table.columns, inches, strict=True):
        column.width = Inches(width)
        for cell in column.cells:
            cell.width = Inches(width)


def header_row(table: Any, theme: Theme, labels: tuple[str, ...]) -> None:
    """Shade a table's first row with the primary colour and set its text white and bold."""
    row = table.rows[0]
    for index, label in enumerate(labels):
        row.cells[index].text = label
        shade_cell(row.cells[index], theme.colour("primary"))
        paragraph = row.cells[index].paragraphs[0]
        set_run_colour(paragraph, theme.colour("text"))
        for run in paragraph.runs:
            run.bold = True


def at_a_glance_table(
    document: Any, theme: Theme, advisory_id: str, severity: str, issued_for: str
) -> None:
    """A 2-column label/value table: Advisory ID, Severity (shaded), Issued for."""
    table = document.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    _kv_row(table, "Advisory ID", advisory_id)
    severity_row = _kv_row(table, "Severity", severity.upper())
    severity_hex = theme.severity_colour(severity)
    shade_cell(severity_row.cells[1], severity_hex)
    set_run_colour(severity_row.cells[1].paragraphs[0], theme.text_on(severity_hex))
    _kv_row(table, "Issued for", issued_for)


def _kv_row(table: Any, label: str, value: str) -> Any:
    """Append one label/value row and return it."""
    row = table.add_row()
    row.cells[0].text = label
    row.cells[1].text = value
    return row


def indicators_table(document: Any, theme: Theme, indicators: list[Any]) -> None:
    """A bordered Type/Value/Note table with a shaded header row."""
    table = document.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    header_row(table, theme, ("Type", "Value", "Note"))
    for indicator in indicators:
        row = table.add_row()
        row.cells[0].text = indicator.ioc_type.value
        row.cells[1].text = indicator.value
        row.cells[2].text = indicator.note or "-"
    _set_column_widths(table, (0.9, 3.0, 2.1))


def actions_table(document: Any, theme: Theme, actions: list[Any]) -> None:
    """A bordered Priority/Action table with the priority cell colour-coded."""
    table = document.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    header_row(table, theme, ("Priority", "Action"))
    for action in actions:
        row = table.add_row()
        priority = action.priority.value
        priority_hex = theme.severity_colour(priority)
        row.cells[0].text = priority.upper()
        shade_cell(row.cells[0], priority_hex)
        set_run_colour(row.cells[0].paragraphs[0], theme.text_on(priority_hex))
        row.cells[1].text = action.action
