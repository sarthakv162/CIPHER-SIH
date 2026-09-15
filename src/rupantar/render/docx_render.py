"""Word rendering for advisory and executive_summary: headings, banner, provenance footer.

Loads the selected template's `.dotx` via python-docx and applies **named paragraph styles**
for headings, the classification/severity banner, and the provenance footer -- never inline
font settings. A missing template, an unopenable `.dotx`, or a style name the template does
not actually define degrades to python-docx's built-in styles (and, for the two styles with
no built-in equivalent, the original inline-bold/plain formatting), recording a warning on
`context` instead of raising. See `docs/TEMPLATES.md` for what a template needs.

On top of that template layer, `render/_docx_theme.py` adds a colour/table design layer --
tinted title/heading runs, a shaded classification banner, a divider rule, an at-a-glance
table, and real bordered tables for the Indicators and Recommended Actions sections -- driven
by the same `Theme` the video/SVG/PDF renderers use. The colour layer degrades independently
of the template layer: a theme problem never blocks a template from rendering, and vice versa.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rupantar.render import _docx_theme as decor
from rupantar.render._theme_fallback import safe_theme
from rupantar.render.context import RenderContext
from rupantar.render.template_registry import DEFAULT_TEMPLATE, get_template, template_file
from rupantar.render.theme import Theme

_BANNER_DEFAULT = "OFFICIAL — DEMO"

# Used only when no template is engaged, or a style name the template maps isn't actually in
# the document -- python-docx's own built-in style names. severity_banner/classification_footer
# have no built-in equivalent: None means "the original inline formatting, not a named style".
_FALLBACK_STYLES: dict[str, str | None] = {
    "title": "Title",
    "heading1": "Heading 1",
    "heading2": "Heading 2",
    "bullet": "List Bullet",
    "severity_banner": None,
    "classification_footer": None,
}
_REQUIRED_STYLES = tuple(_FALLBACK_STYLES)


def render_docx(artefact: Any, path: Path, *, context: RenderContext | None = None) -> None:
    """Render an advisory or executive summary to a .docx file at `path`."""
    from docx import Document

    theme = safe_theme(context)
    template_path, template_styles = _resolve_template(context)
    document, style_map = _open_document(Document, template_path, template_styles, context)
    styles = _resolve_styles(document, style_map, context)

    _banner(document, artefact, styles, theme, context)
    title = _paragraph(document, artefact.title, style=styles["title"])
    _decorate_title(title, theme, context)

    if str(artefact.artefact_type) == "advisory":
        _advisory_body(document, artefact, styles, theme, context)
    else:
        _executive_summary_body(document, artefact, styles, theme, context)

    footer = document.sections[0].footer.paragraphs[0]
    footer.text = f"Provenance: {path.name}.manifest.json"
    if styles["classification_footer"]:
        footer.style = document.styles[styles["classification_footer"]]
    document.save(str(path))


def _decorate_title(title: Any, theme: Theme, context: RenderContext | None) -> None:
    """Tint the title run and add a coloured divider rule beneath it; never raises."""
    try:
        decor.set_run_colour(title, theme.colour("primary"))
        decor.bottom_border(title, theme.colour("accent"))
    except Exception as exc:  # a decoration slip must never block the document
        _warn(context, f"title decoration skipped ({exc})")


def _resolve_template(context: RenderContext | None) -> tuple[Path | None, dict[str, str]]:
    """The `.dotx` file and its declared style map, or (None, {}) to use the built-in document."""
    template_id = context.template_id if context else DEFAULT_TEMPLATE
    configs_dir = context.configs_dir if context else None
    spec = get_template(template_id, configs_dir=configs_dir)
    if spec is None:
        if template_id != DEFAULT_TEMPLATE:
            _warn(context, f"template {template_id!r} is not defined; using the built-in styles")
        return None, {}
    if spec.docx is None:
        _warn(context, f"template {template_id!r} has no docx binding; using the built-in styles")
        return None, {}
    path = template_file(configs_dir, spec.docx.file)
    if not path.is_file():
        _warn(context, f"template {template_id!r}'s file {spec.docx.file!r} is missing")
        return None, {}
    return path, dict(spec.docx.styles)


def _open_document(
    document_cls: Any,
    template_path: Path | None,
    template_styles: dict[str, str],
    context: RenderContext | None,
) -> tuple[Any, dict[str, str]]:
    """Open `template_path` if given, else a blank document; return it with its style map."""
    if template_path is not None:
        try:
            return document_cls(str(template_path)), template_styles
        except Exception as exc:  # a corrupt or unreadable .dotx must never crash the job
            _warn(context, f"template file {template_path.name!r} could not be opened ({exc})")
    return document_cls(), {}


def _resolve_styles(
    document: Any, style_map: dict[str, str], context: RenderContext | None
) -> dict[str, str | None]:
    """Every required style key mapped to a style genuinely present in `document`."""
    available = {style.name for style in document.styles}
    resolved: dict[str, str | None] = {}
    for key in _REQUIRED_STYLES:
        name = style_map.get(key)
        if name and name in available:
            resolved[key] = name
            continue
        if name:
            _warn(context, f"template style {key!r}={name!r} not found in the document")
        resolved[key] = _FALLBACK_STYLES[key]
    return resolved


def _warn(context: RenderContext | None, message: str) -> None:
    """Record a degradation warning on the shared context, if one was given."""
    if context is not None:
        context.warnings.append(message)


def _paragraph(document: Any, text: str, *, style: str | None, bold: bool = False) -> Any:
    """Add one paragraph, styled by name when given, else with the original inline formatting."""
    if style:
        return document.add_paragraph(text, style=style)
    paragraph = document.add_paragraph(text)
    if bold and paragraph.runs:
        paragraph.runs[0].bold = True
    return paragraph


def _coloured_heading(
    document: Any,
    text: str,
    styles: dict[str, str | None],
    theme: Theme,
    context: RenderContext | None,
) -> None:
    """A heading-1 paragraph, tinted with the theme's primary colour."""
    paragraph = _paragraph(document, text, style=styles["heading1"])
    try:
        decor.set_run_colour(paragraph, theme.colour("primary"))
    except Exception as exc:
        _warn(context, f"heading colour skipped ({exc})")


def _executive_summary_body(
    document: Any,
    a: Any,
    styles: dict[str, str | None],
    theme: Theme,
    context: RenderContext | None,
) -> None:
    """Fill a Word document with executive-summary content."""
    document.add_paragraph(a.headline).runs[0].italic = True
    document.add_paragraph(a.context)
    _bullet_section(document, "Key points", a.key_points, styles, theme, context)
    _bullet_section(document, "Implications", a.implications, styles, theme, context)
    _bullet_section(document, "Recommended actions", a.recommended_actions, styles, theme, context)
    _coloured_heading(document, "Takeaway", styles, theme, context)
    document.add_paragraph(a.one_line_takeaway)


def _advisory_body(
    document: Any,
    a: Any,
    styles: dict[str, str | None],
    theme: Theme,
    context: RenderContext | None,
) -> None:
    """Fill a Word document with advisory content."""
    _at_a_glance(document, a, theme, context)
    _coloured_heading(document, "Summary", styles, theme, context)
    document.add_paragraph(a.summary)
    _coloured_heading(document, "Background", styles, theme, context)
    document.add_paragraph(a.background)
    _coloured_heading(document, "Technical details", styles, theme, context)
    for detail in a.technical_details:
        _paragraph(document, detail.heading, style=styles["heading2"])
        document.add_paragraph(detail.body)
    _bullet_section(document, "Affected entities", a.affected_entities, styles, theme, context)
    _coloured_heading(document, "Indicators", styles, theme, context)
    _indicators_section(document, a.indicators, theme, context)
    _coloured_heading(document, "Recommended actions", styles, theme, context)
    _actions_section(document, a.recommended_actions, theme, context)
    _bullet_section(document, "References", a.references, styles, theme, context)
    document.add_paragraph(f"Handling: {a.handling_caveat}").runs[0].italic = True


def _at_a_glance(document: Any, a: Any, theme: Theme, context: RenderContext | None) -> None:
    """The Advisory ID / Severity / Issued-for table, or nothing on a decoration failure."""
    try:
        decor.at_a_glance_table(document, theme, a.advisory_id, a.severity.value, a.issued_for)
    except Exception as exc:
        _warn(context, f"at-a-glance table skipped ({exc})")
        for label, value in (
            ("Advisory ID", a.advisory_id),
            ("Severity", a.severity.value),
            ("Issued for", a.issued_for),
        ):
            document.add_paragraph(f"{label}: {value}")


def _indicators_section(
    document: Any, indicators: list[Any], theme: Theme, context: RenderContext | None
) -> None:
    """A real Type/Value/Note table, or the original bulleted list on a build failure."""
    if not indicators:
        document.add_paragraph("none provided")
        return
    try:
        decor.indicators_table(document, theme, indicators)
    except Exception as exc:
        _warn(context, f"indicators table could not be built ({exc}); using a bulleted list")
        for indicator in indicators:
            note = f" — {indicator.note}" if indicator.note else ""
            document.add_paragraph(f"{indicator.ioc_type.value}: {indicator.value}{note}")


def _actions_section(
    document: Any, actions: list[Any], theme: Theme, context: RenderContext | None
) -> None:
    """A real Priority/Action table, or the original bulleted list on a build failure."""
    if not actions:
        document.add_paragraph("none")
        return
    try:
        decor.actions_table(document, theme, actions)
    except Exception as exc:
        _warn(context, f"actions table could not be built ({exc}); using a bulleted list")
        for action in actions:
            document.add_paragraph(f"[{action.priority.value}] {action.action}")


def _bullet_section(
    document: Any,
    heading: str,
    items: list[Any],
    styles: dict[str, str | None],
    theme: Theme,
    context: RenderContext | None,
) -> None:
    """A tinted heading-1 paragraph and one bulleted paragraph per item."""
    _coloured_heading(document, heading, styles, theme, context)
    for item in items:
        document.add_paragraph(str(item), style=styles["bullet"])


def _banner(
    document: Any,
    artefact: Any,
    styles: dict[str, str | None],
    theme: Theme,
    context: RenderContext | None,
) -> None:
    """Add the classification/confidence banner as the document's first paragraph, shaded."""
    text = artefact.confidence_notes.strip() or _BANNER_DEFAULT
    paragraph = _paragraph(document, text, style=styles["severity_banner"], bold=True)
    try:
        decor.shade_paragraph(paragraph, theme.colour("primary"))
        decor.set_run_colour(paragraph, theme.colour("text"))
    except Exception as exc:
        _warn(context, f"banner shading skipped ({exc})")
