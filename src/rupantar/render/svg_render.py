"""SVG infographic from an InfographicSpec via an inline Jinja2 template, styled by the theme."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rupantar.render.theme import load_theme

_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350">
  <rect width="1080" height="1350" fill="{{ c.background }}"/>
  <text x="60" y="110" font-family="sans-serif" font-size="{{ t.display }}" font-weight="bold"
        fill="{{ c.text }}">{{ headline }}</text>
  <text x="60" y="160" font-family="sans-serif" font-size="{{ t.body }}"
        fill="{{ c.text_muted }}">{{ subhead }}</text>
  {% for s in sections %}
  <g transform="translate(60, {{ 240 + loop.index0 * 190 }})">
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
  <g transform="translate(60, {{ 260 + sections|length * 190 }})">
    {% for m in key_messages %}
    <text x="0" y="{{ loop.index0 * 36 }}" font-family="sans-serif" font-size="{{ t.body }}"
          fill="{{ c.text }}">&#8226; {{ m }}</text>
    {% endfor %}
  </g>
  <text x="60" y="1310" font-family="sans-serif" font-size="{{ t.footer }}"
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
    template = jinja2.Environment(autoescape=True, undefined=jinja2.StrictUndefined).from_string(
        _TEMPLATE
    )
    svg = template.render(
        c=colours,
        t=scale,
        headline=artefact.headline,
        subhead=artefact.subhead,
        sections=artefact.sections,
        key_messages=artefact.key_messages,
        footer=artefact.footer,
    )
    path.write_text(svg, encoding="utf-8")
