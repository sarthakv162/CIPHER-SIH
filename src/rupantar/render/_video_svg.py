"""Theme-driven 1280x720 panel rendering via Jinja2 SVG + `resvg_py` rasterisation.

This is the primary panel path (Phase 9c); `render/panels.py`'s Pillow renderer is the fallback
a caller reaches for on any failure here (bad font, malformed markup, a resvg internal error).
Backgrounds and the infographic hero art are embedded as base64 PNG data URIs so nothing needs
external file resolution at render time -- the safer offline choice per the Phase 9c brief.
`jinja2` and `resvg_py` are imported inside functions (INV-3).
"""

from __future__ import annotations

import base64
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rupantar.render.theme import Theme

CANVAS = (1280, 720)
MARGIN = 64
_USABLE_WIDTH = CANVAS[0] - 2 * MARGIN
_CHAR_WIDTH_FACTOR = 0.56
_LAYOUTS = ("title_card", "statement", "stat_block", "quote", "closing", "infographic_hero")

_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="1280" height="720" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="{{ c.background }}"/>
  {% if background_uri %}
  <image x="0" y="0" width="1280" height="720" xlink:href="{{ background_uri }}"
         preserveAspectRatio="{{ background_par }}"/>
  {% endif %}
  {% if scrim %}
  <rect width="1280" height="720" fill="{{ scrim }}"/>
  {% endif %}
  {% if rule %}
  <rect x="{{ rule.x }}" y="{{ rule.y }}" width="{{ rule.w }}" height="6" fill="{{ c.accent }}"/>
  {% endif %}
  {% if lower_third %}
  <rect x="0" y="{{ lower_third.top }}" width="1280" height="52" fill="{{ c.surface }}"/>
  <rect x="0" y="{{ lower_third.top }}" width="8" height="52" fill="{{ c.accent }}"/>
  {% if lower_third.chip %}
  <rect x="{{ lower_third.chip.x }}" y="{{ lower_third.top + 5 }}" width="{{ lower_third.chip.w }}"
        height="32" fill="{{ lower_third.chip.fill }}"/>
  {% endif %}
  {% endif %}
  {% for op in text_ops %}
  <text x="{{ op.x }}" y="{{ op.y }}" font-family="sans-serif" font-size="{{ op.size }}"
        text-anchor="{{ op.anchor }}"
        {% if op.weight == 'bold' %}font-weight="bold"{% endif %}
        fill="{{ op.fill }}">{{ op.text }}</text>
  {% endfor %}
</svg>
"""


@dataclass
class _TextOp:
    """One `<text>` element already wrapped to a single line."""

    x: int
    y: int
    size: int
    fill: str
    text: str
    weight: str = "normal"
    anchor: str = "start"


def _wrap(text: str, font_px: int, max_lines: int, *, max_width: int = _USABLE_WIDTH) -> list[str]:
    """Heuristic pixel-width word wrap (no font metrics available before rasterisation)."""
    text = (text or "").strip()
    if not text:
        return []
    chars = max(6, int(max_width / (font_px * _CHAR_WIDTH_FACTOR)))
    lines = textwrap.wrap(text, width=chars) or [text]
    return lines[:max_lines] if len(lines) > max_lines else lines


def _mime_of(data: bytes) -> str:
    """Sniff PNG vs JPEG from magic bytes; default to PNG for anything else."""
    return "image/jpeg" if data[:2] == b"\xff\xd8" else "image/png"


def _bytes_data_uri(data: bytes) -> str:
    """A `data:` URI embedding raw image bytes as base64."""
    return f"data:{_mime_of(data)};base64,{base64.b64encode(data).decode('ascii')}"


def _file_data_uri(path: Path) -> str:
    """A `data:` URI embedding an on-disk image file's bytes as base64."""
    return _bytes_data_uri(path.read_bytes())


@dataclass
class _Ops:
    """Text ops plus the accent rule position, threaded through the layout builders."""

    text: list[_TextOp] = field(default_factory=list)
    rule: dict[str, int] | None = None


def _title_block(theme: Theme, title: str, *, centered: bool) -> tuple[_Ops, int]:
    """Title lines plus the accent rule beneath them; returns ops and the next top y."""
    size = theme.px("title")
    lines = _wrap(title.strip() or "Untitled", size, 3)
    anchor = "middle" if centered else "start"
    x = CANVAS[0] // 2 if centered else MARGIN
    y = MARGIN + 12 + size
    ops = [
        _TextOp(x, y + i * int(size * 1.2), size, theme.colour("text"), line, "bold", anchor)
        for i, line in enumerate(lines)
    ]
    rule_y = y + max(0, len(lines) - 1) * int(size * 1.2) + 22
    rule_x = (CANVAS[0] - 220) // 2 if centered else MARGIN
    rule = {"x": rule_x, "y": rule_y, "w": 220}
    return _Ops(ops, rule), rule_y + 34


def _paragraph(
    theme: Theme, lines: list[str], top: int, *, size_name: str, fill: str, centered: bool = False
) -> list[_TextOp]:
    """A left- or centre-aligned wrapped paragraph starting at `top`."""
    size = theme.px(size_name)
    anchor = "middle" if centered else "start"
    x = CANVAS[0] // 2 if centered else MARGIN
    ops: list[_TextOp] = []
    y = top + size
    for raw in lines or [""]:
        for line in _wrap(raw, size, 20):
            if y > CANVAS[1] - 150:
                return ops
            ops.append(_TextOp(x, y, size, fill, line, "normal", anchor))
            y += int(size * 1.45)
    return ops


def _body_centered(theme: Theme, lines: list[str], top: int) -> list[_TextOp]:
    """Title-card / closing body: a centred logline in muted heading-size text."""
    size = theme.px("heading")
    wrapped = [
        line
        for raw in (lines or [""])
        for line in _wrap(raw, size, 20, max_width=CANVAS[0] - 3 * MARGIN)
    ]
    y = max(top, (CANVAS[1] - len(wrapped) * int(size * 1.4)) // 2) + size
    return [
        _TextOp(
            CANVAS[0] // 2,
            y + i * int(size * 1.4),
            size,
            theme.colour("text_muted"),
            line,
            "normal",
            "middle",
        )
        for i, line in enumerate(wrapped)
    ]


def _body_stat(theme: Theme, lines: list[str], top: int) -> list[_TextOp]:
    """Oversized figure plus label lines beneath it."""
    figure = (lines[0] if lines else "--")[:12]
    label_lines = lines[1:] or (lines[:1] if len(lines) == 1 else ["figure"])
    fig_size = theme.px("display")
    ops = [_TextOp(MARGIN, top + fig_size, fig_size, theme.colour("accent"), figure, "bold")]
    ops += _paragraph(
        theme, label_lines, top + 20 + fig_size, size_name="heading", fill=theme.colour("text")
    )
    return ops


def _body_quote(theme: Theme, lines: list[str], top: int) -> list[_TextOp]:
    """A large opening quote mark followed by the wrapped quotation."""
    mark_size = theme.px("display")
    ops = [
        _TextOp(MARGIN - 8, top + mark_size - 30, mark_size, theme.colour("accent"), "“", "bold")
    ]
    body = " ".join(lines).strip('"“”')
    heading = theme.px("heading")
    y = top + 90 + heading
    for line in _wrap(body, heading, 6, max_width=CANVAS[0] - 2 * MARGIN - 40)[:6]:
        ops.append(_TextOp(MARGIN + 24, y, heading, theme.colour("text"), line, "bold"))
        y += int(heading * 1.4)
    return ops


def _body_hero_fallback(theme: Theme, lines: list[str], top: int) -> list[_TextOp]:
    """Subhead plus bulleted section labels, used only when hero art is unavailable."""
    ops = _paragraph(theme, lines[:1], top, size_name="heading", fill=theme.colour("text"))
    bullet_top = top + theme.px("heading") + theme.step(3)
    bullets = [f"• {raw}" for raw in lines[1:8]]
    ops += _paragraph(theme, bullets, bullet_top, size_name="body", fill=theme.colour("text_muted"))
    return ops


_BODY = {
    "title_card": _body_centered,
    "closing": _body_centered,
    "statement": lambda theme, lines, top: _paragraph(
        theme, lines, top, size_name="heading", fill=theme.colour("text")
    ),
    "stat_block": _body_stat,
    "quote": _body_quote,
    "infographic_hero": _body_hero_fallback,
}


def _scene_indicator(theme: Theme, index: int, count: int) -> _TextOp:
    """`SCENE n / N` marker, top-right."""
    size = theme.px("caption")
    text = f"SCENE {index} / {count}" if count else f"SCENE {index}"
    return _TextOp(
        CANVAS[0] - MARGIN,
        MARGIN - 24 + size,
        size,
        theme.colour("text_muted"),
        text,
        "normal",
        "end",
    )


def _footer_ops(theme: Theme, footer: str, wordmark: str) -> list[_TextOp]:
    """Persistent footer: artefact id at left, wordmark at right."""
    size = theme.px("footer")
    y = CANVAS[1] - 34 + size
    ops = [_TextOp(MARGIN, y, size, theme.colour("text_muted"), footer[:80], "normal", "start")]
    if wordmark:
        ops.append(
            _TextOp(
                CANVAS[0] - MARGIN, y, size, theme.colour("text_muted"), wordmark, "normal", "end"
            )
        )
    return ops


def _chip_width(text: str, size: int) -> int:
    """Heuristic chip width from the same average-glyph-width estimate as `_wrap`."""
    return int(len(text) * size * _CHAR_WIDTH_FACTOR) + 28


def _lower_third(
    theme: Theme, lower_third: tuple[str, str]
) -> tuple[dict[str, Any], list[_TextOp]]:
    """The lower-third bar template vars plus its label/chip text ops."""
    label, severity = lower_third
    top = CANVAS[1] - 96
    caption = theme.px("caption")
    ops = [
        _TextOp(
            MARGIN, top + 15 + caption, caption, theme.colour("text"), label.upper()[:60], "bold"
        )
    ]
    layer: dict[str, Any] = {"top": top, "chip": None}
    if severity.strip():
        text = severity.upper()[:12]
        width = _chip_width(text, caption)
        x = CANVAS[0] - MARGIN - width
        fill = theme.severity_colour(severity)
        layer["chip"] = {"x": x, "w": width, "fill": fill}
        ops.append(_TextOp(x + 14, top + 15 + caption, caption, theme.text_on(fill), text, "bold"))
    return layer, ops


def hero_background_png(spec: Any, theme: Theme) -> bytes:
    """Rasterise the real infographic SVG for use as the hero panel's cropped background art."""
    import resvg_py

    from rupantar.render.svg_render import render_svg_string

    svg = render_svg_string(spec, theme=theme)
    return bytes(resvg_py.svg_to_bytes(svg_string=svg, font_files=_font_files(theme)))


def _font_files(theme: Theme) -> list[str]:
    """Existing theme font-file candidates, as hints for resvg's font matching."""
    return [p for p in (theme.font_path("regular"), theme.font_path("bold")) if p]


def _background_and_scrim(
    theme: Theme, chosen: str, hero_spec: Any, background: Path | None, scrim: bool
) -> tuple[str | None, str, str | None, bool]:
    """Resolve the background image URI, its fit mode, any scrim colour, and hero-art use."""
    hero_png = (
        hero_background_png(hero_spec, theme)
        if chosen == "infographic_hero" and hero_spec
        else None
    )
    background_uri = None
    background_par = "xMidYMid slice"
    scrim_colour = None
    if hero_png is not None:
        background_uri = _bytes_data_uri(hero_png)
        background_par = "xMidYMin slice"
    elif background is not None and Path(background).is_file():
        background_uri = _file_data_uri(Path(background))
    if background_uri is not None and (scrim or hero_png is not None):
        r, g, b = theme.rgb("primary")
        wash = (int(r * 0.35), int(g * 0.35), int(b * 0.35))
        alpha = 0.62 if hero_png is not None else 0.80
        scrim_colour = f"rgba({wash[0]},{wash[1]},{wash[2]},{alpha})"
    return background_uri, background_par, scrim_colour, hero_png is not None


def render_svg_panel(
    target: Path,
    *,
    layout: str,
    title: str,
    body_lines: list[str],
    scene_index: int,
    scene_count: int,
    footer: str,
    theme: Theme,
    background: Path | None = None,
    scrim: bool = False,
    lower_third: tuple[str, str] | None = None,
    hero_spec: Any | None = None,
) -> None:
    """Render one panel PNG for `layout` via SVG + resvg; raises on failure (caller degrades)."""
    import jinja2
    import resvg_py

    chosen = layout if layout in _LAYOUTS else "statement"
    background_uri, background_par, scrim_colour, has_hero_art = _background_and_scrim(
        theme, chosen, hero_spec, background, scrim
    )
    text_ops: list[_TextOp] = []
    rule = None
    if not has_hero_art:
        centered = chosen in ("title_card", "closing")
        title_ops, top = _title_block(theme, title, centered=centered)
        text_ops += title_ops.text
        rule = title_ops.rule
        text_ops += _BODY[chosen](theme, [line for line in body_lines if line], top)
    text_ops.append(_scene_indicator(theme, scene_index, scene_count))
    lower_layer = None
    if lower_third is not None:
        lower_layer, lower_ops = _lower_third(theme, lower_third)
        text_ops += lower_ops
    text_ops += _footer_ops(theme, footer, theme.wordmark.text)

    env = jinja2.Environment(autoescape=True, undefined=jinja2.StrictUndefined)
    svg = env.from_string(_TEMPLATE).render(
        c={
            "background": theme.colour("background"),
            "surface": theme.colour("surface"),
            "accent": theme.colour("accent"),
        },
        background_uri=background_uri,
        background_par=background_par,
        scrim=scrim_colour,
        text_ops=[op.__dict__ for op in text_ops],
        rule=rule,
        lower_third=lower_layer,
    )
    png = resvg_py.svg_to_bytes(
        svg_string=svg, width=CANVAS[0], height=CANVAS[1], font_files=_font_files(theme)
    )
    target.write_bytes(png)
