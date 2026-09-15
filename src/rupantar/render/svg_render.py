"""SVG infographic from an InfographicSpec via an inline Jinja2 template, styled by the theme.

Every free-text field (headline, subhead, section body, key messages) is word-wrapped in Python
before it ever reaches the template: SVG does not wrap text on its own, so an unwrapped long
sentence used to run straight off the 1080px canvas. Wrapping uses a heuristic average glyph
width (no font-metrics library, no rasteriser -- see MEMORY.md) rather than exact measurement,
which is precise enough to keep every line inside the canvas with a small safety margin. Section
blocks stack at a height computed from their own wrapped line count, so a longer body paragraph
pushes the next section down instead of overlapping it.

A real chart -- a horizontal bar series or a timeline strip -- is drawn between the subhead
and the per-section stat cards whenever `extract_chart_data` finds genuinely parseable numbers
on a comparable scale, using the same never-fabricate extraction the video hero panel uses
(`render.charts`).
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rupantar.render.charts import ChartData, extract_chart_data, wrap_label
from rupantar.render.theme import Theme, load_theme

_CANVAS_WIDTH = 1080
_MARGIN_X = 60
_USABLE_WIDTH = _CANVAS_WIDTH - 2 * _MARGIN_X
_CHAR_WIDTH_FACTOR = 0.56  # heuristic average glyph advance as a fraction of font-size
_CHART_GAP = 50
_SECTION_GAP = 36
_MIN_HEIGHT = 1350
_FOOTER_MARGIN = 40

_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="{{ height }}"
     viewBox="0 0 1080 {{ height }}">
  <rect width="1080" height="{{ height }}" fill="{{ c.background }}"/>
  {% for op in text_ops %}
  <text x="{{ op.x }}" y="{{ op.y }}" font-family="sans-serif" font-size="{{ op.size }}"
        {% if op.weight == 'bold' %}font-weight="bold"{% endif %}
        fill="{{ op.fill }}">{{ op.text }}</text>
  {% endfor %}
  {% if chart %}
  <g transform="translate(60, {{ chart.top }})">
    {% if chart.kind == 'bar' %}
    {% for b in chart.bars %}
    <text x="0" y="{{ b.y + b.h - 8 }}" font-family="sans-serif" font-size="{{ t.caption }}"
          fill="{{ c.text_muted }}">{{ b.label }}</text>
    <rect x="{{ chart.axis_x }}" y="{{ b.y }}" width="{{ b.w }}" height="{{ b.h }}" rx="4"
          fill="{{ c.accent }}"/>
    <text x="{{ chart.axis_x + b.w + 12 }}" y="{{ b.y + b.h - 8 }}" font-family="sans-serif"
          font-size="{{ t.caption }}" fill="{{ c.text }}">{{ b.value_text }}</text>
    {% endfor %}
    {% else %}
    <line x1="0" y1="20" x2="{{ chart.width }}" y2="20" stroke="{{ c.surface }}"
          stroke-width="3"/>
    {% for n in chart.nodes %}
    <circle cx="{{ n.cx }}" cy="20" r="8" fill="{{ c.accent }}"/>
    {% for line in n.lines %}
    <text x="{{ n.cx - 55 }}" y="{{ 50 + loop.index0 * 20 }}" font-family="sans-serif"
          font-size="{{ t.caption }}" fill="{{ c.text_muted }}">{{ line }}</text>
    {% endfor %}
    {% endfor %}
    {% endif %}
  </g>
  {% endif %}
  <text x="60" y="{{ height - 40 }}" font-family="sans-serif" font-size="{{ t.footer }}"
        fill="{{ c.text_muted }}">{{ footer }}</text>
</svg>
"""


@dataclass
class _TextOp:
    """One `<text>` element: position, size, weight and fill, already wrapped to one line."""

    x: int
    y: int
    size: int
    fill: str
    text: str
    weight: str = "normal"


def _wrap(text: str, font_px: int, max_lines: int) -> list[str]:
    """Word-wrap `text` to the canvas's usable width at `font_px`, capped at `max_lines`."""
    text = (text or "").strip()
    if not text:
        return []
    chars = max(10, int(_USABLE_WIDTH / (font_px * _CHAR_WIDTH_FACTOR)))
    lines = textwrap.wrap(text, width=chars) or [text]
    if len(lines) <= max_lines:
        return lines
    kept = lines[: max_lines - 1]
    tail = " ".join(lines[max_lines - 1 :])[: chars - 1].rstrip()
    kept.append(f"{tail}…")
    return kept


def _block(
    lines: list[str], *, x: int, top: int, size: int, fill: str, weight: str = "normal"
) -> tuple[list[_TextOp], int]:
    """Stack `lines` as text ops starting at `top`; return the ops and the block's height."""
    line_height = int(size * 1.25)
    ops = [
        _TextOp(x=x, y=top + size + i * line_height, size=size, fill=fill, text=line, weight=weight)
        for i, line in enumerate(lines)
    ]
    height = max(1, len(lines)) * line_height
    return ops, height


def render_svg(artefact: Any, path: Path) -> None:
    """Render the infographic spec to an SVG file at `path`, styled by the ntro-formal theme."""
    path.write_text(render_svg_string(artefact), encoding="utf-8")


def render_svg_string(artefact: Any, *, theme: Theme | None = None) -> str:
    """Build the infographic spec's SVG markup (no file write) -- reused by the video hero panel."""
    import jinja2

    theme = theme or load_theme()
    colours = {
        name: theme.colour(name)
        for name in ("background", "surface", "text", "text_muted", "accent")
    }
    scale = {name: theme.px(name) for name in ("display", "title", "heading", "body", "caption")}
    scale["footer"] = theme.px("footer")
    # keep the headline legible: the panel display size is oversized for 1080px wide
    scale["display"] = min(scale["display"], 56)
    scale["title"] = min(scale["title"], 46)

    text_ops: list[_TextOp] = []
    top = 70
    headline_ops, headline_h = _block(
        _wrap(artefact.headline, scale["display"], max_lines=2),
        x=_MARGIN_X,
        top=top,
        size=scale["display"],
        fill=colours["text"],
        weight="bold",
    )
    text_ops += headline_ops
    top += headline_h + 14
    subhead_ops, subhead_h = _block(
        _wrap(artefact.subhead, scale["body"], max_lines=2),
        x=_MARGIN_X,
        top=top,
        size=scale["body"],
        fill=colours["text_muted"],
    )
    text_ops += subhead_ops
    top += subhead_h

    chart = _chart_geometry(extract_chart_data(artefact))
    chart_top = top + 20
    top = chart_top + (0 if chart is None else chart["height"] + _CHART_GAP)

    for section in artefact.sections:
        top = _section_block(text_ops, section, theme, scale, colours, top)

    for message in artefact.key_messages:
        lines = _wrap(f"• {message}", scale["body"], max_lines=2)
        ops, height = _block(lines, x=_MARGIN_X, top=top, size=scale["body"], fill=colours["text"])
        text_ops += ops
        top += height

    height = max(_MIN_HEIGHT, top + _FOOTER_MARGIN * 2)
    if chart is not None:
        chart["top"] = chart_top

    template = jinja2.Environment(autoescape=True, undefined=jinja2.StrictUndefined).from_string(
        _TEMPLATE
    )
    svg = template.render(
        c=colours,
        t=scale,
        height=height,
        text_ops=[op.__dict__ for op in text_ops],
        chart=chart,
        footer=artefact.footer,
    )
    return str(svg)


def _section_block(
    text_ops: list[_TextOp],
    section: Any,
    theme: Theme,
    scale: dict[str, int],
    colours: dict[str, str],
    top: int,
) -> int:
    """Append one stat-card's text ops (value, label, body, heading) and return the next `top`."""
    value_ops, value_h = _block(
        _wrap(section.stat_value, scale["title"], max_lines=1),
        x=_MARGIN_X,
        top=top,
        size=scale["title"],
        fill=colours["accent"],
        weight="bold",
    )
    text_ops += value_ops
    top += value_h
    label_ops, label_h = _block(
        _wrap(section.stat_label, scale["heading"], max_lines=1),
        x=_MARGIN_X,
        top=top,
        size=scale["heading"],
        fill=colours["text"],
    )
    text_ops += label_ops
    top += label_h
    body_ops, body_h = _block(
        _wrap(section.body, scale["caption"], max_lines=3),
        x=_MARGIN_X,
        top=top,
        size=scale["caption"],
        fill=colours["text_muted"],
    )
    text_ops += body_ops
    top += body_h
    heading_ops, heading_h = _block(
        _wrap(section.heading, scale["footer"], max_lines=1),
        x=_MARGIN_X,
        top=top,
        size=scale["footer"],
        fill=colours["text_muted"],
    )
    text_ops += heading_ops
    return top + heading_h + _SECTION_GAP


def _chart_geometry(data: ChartData | None) -> dict[str, Any] | None:
    """Pixel layout for `data` in the 1080-wide SVG canvas, or None when there is nothing."""
    if data is None:
        return None
    return _bar_geometry(data) if data.kind == "bar" else _timeline_geometry(data)


def _bar_geometry(data: ChartData) -> dict[str, Any]:
    """One row per point, bar width scaled to the largest absolute value."""
    axis_x, row_h, bar_h = 220, 54, 30
    width = 1080 - 60 - 60 - axis_x
    peak = max((abs(value) for _, value in data.points), default=1.0) or 1.0
    bars = [
        {
            "label": label[:24],
            "value_text": f"{value:g}",
            "y": index * row_h,
            "w": max(4, width * (abs(value) / peak)),
            "h": bar_h,
        }
        for index, (label, value) in enumerate(data.points)
    ]
    return {"kind": "bar", "top": 0, "height": len(bars) * row_h, "axis_x": axis_x, "bars": bars}


def _timeline_geometry(data: ChartData) -> dict[str, Any]:
    """Evenly spaced nodes with wrapped labels along a single horizontal strip."""
    width = 1080 - 60 - 60
    count = max(1, len(data.labels))
    step = width / (count - 1) if count > 1 else 0
    nodes = [
        {"cx": int(step * index) if count > 1 else width // 2, "lines": wrap_label(label)}
        for index, label in enumerate(data.labels)
    ]
    return {"kind": "timeline", "top": 0, "height": 90, "width": width, "nodes": nodes}
