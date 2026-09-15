"""SVG infographic from an InfographicSpec via an inline Jinja2 template, styled by the theme.

A real chart -- a horizontal bar series or a timeline strip -- is drawn between the subhead
and the per-section stat cards whenever `extract_chart_data` finds genuinely parseable
numbers, using the same never-fabricate extraction the video hero panel uses (`render.charts`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rupantar.render.charts import ChartData, extract_chart_data, wrap_label
from rupantar.render.theme import load_theme

_CHART_TOP = 190
_SECTIONS_TOP_DEFAULT = 240
_CHART_GAP = 50
_MIN_HEIGHT = 1350
_FOOTER_MARGIN = 40

_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="{{ height }}"
     viewBox="0 0 1080 {{ height }}">
  <rect width="1080" height="{{ height }}" fill="{{ c.background }}"/>
  <text x="60" y="110" font-family="sans-serif" font-size="{{ t.display }}" font-weight="bold"
        fill="{{ c.text }}">{{ headline }}</text>
  <text x="60" y="160" font-family="sans-serif" font-size="{{ t.body }}"
        fill="{{ c.text_muted }}">{{ subhead }}</text>
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
  {% for s in sections %}
  <g transform="translate(60, {{ sections_top + loop.index0 * 190 }})">
    <text x="0" y="0" font-family="sans-serif" font-size="{{ t.title }}" font-weight="bold"
          fill="{{ c.accent }}">{{ s.stat_value }}</text>
    <text x="0" y="38" font-family="sans-serif" font-size="{{ t.heading }}"
          fill="{{ c.text }}">{{ s.stat_label }}</text>
    <text x="0" y="74" font-family="sans-serif" font-size="{{ t.caption }}"
          fill="{{ c.text_muted }}">{{ s.body }}</text>
    <text x="0" y="104" font-family="sans-serif" font-size="{{ t.footer }}"
          fill="{{ c.text_muted }}">{{ s.heading }}</text>
  </g>
  {% endfor %}
  <g transform="translate(60, {{ sections_top + 20 + sections|length * 190 }})">
    {% for m in key_messages %}
    <text x="0" y="{{ loop.index0 * 36 }}" font-family="sans-serif" font-size="{{ t.body }}"
          fill="{{ c.text }}">&#8226; {{ m }}</text>
    {% endfor %}
  </g>
  <text x="60" y="{{ height - 40 }}" font-family="sans-serif" font-size="{{ t.footer }}"
        fill="{{ c.text_muted }}">{{ footer }}</text>
</svg>
"""


def render_svg(artefact: Any, path: Path) -> None:
    """Render the infographic spec to an SVG file at `path`, styled by the ntro-formal theme."""
    import jinja2

    theme = load_theme()
    colours = {
        name: theme.colour(name)
        for name in ("background", "surface", "text", "text_muted", "accent")
    }
    scale = {name: theme.px(name) for name in ("display", "title", "heading", "body", "caption")}
    scale["footer"] = theme.px("footer")
    # keep the SVG headline legible: the panel display size is oversized for 1080px wide
    scale["display"] = min(scale["display"], 56)
    scale["title"] = min(scale["title"], 46)

    chart = _chart_geometry(extract_chart_data(artefact))
    sections_top = (
        _SECTIONS_TOP_DEFAULT if chart is None else chart["top"] + chart["height"] + _CHART_GAP
    )
    messages_top = sections_top + 20 + len(artefact.sections) * 190
    content_bottom = messages_top + len(artefact.key_messages) * 36
    height = max(_MIN_HEIGHT, content_bottom + _FOOTER_MARGIN * 2)

    template = jinja2.Environment(autoescape=True, undefined=jinja2.StrictUndefined).from_string(
        _TEMPLATE
    )
    svg = template.render(
        c=colours,
        t=scale,
        height=height,
        headline=artefact.headline,
        subhead=artefact.subhead,
        chart=chart,
        sections=artefact.sections,
        sections_top=sections_top,
        key_messages=artefact.key_messages,
        footer=artefact.footer,
    )
    path.write_text(svg, encoding="utf-8")


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
    return {
        "kind": "bar",
        "top": _CHART_TOP,
        "height": len(bars) * row_h,
        "axis_x": axis_x,
        "bars": bars,
    }


def _timeline_geometry(data: ChartData) -> dict[str, Any]:
    """Evenly spaced nodes with wrapped labels along a single horizontal strip."""
    width = 1080 - 60 - 60
    count = max(1, len(data.labels))
    step = width / (count - 1) if count > 1 else 0
    nodes = [
        {"cx": int(step * index) if count > 1 else width // 2, "lines": wrap_label(label)}
        for index, label in enumerate(data.labels)
    ]
    return {"kind": "timeline", "top": _CHART_TOP, "height": 90, "width": width, "nodes": nodes}
