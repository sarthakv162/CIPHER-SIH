"""SVG infographic from an InfographicSpec via an inline Jinja2 template."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350">
  <rect width="1080" height="1350" fill="#0b1f33"/>
  <text x="60" y="110" font-family="sans-serif" font-size="52" font-weight="bold"
        fill="#ffffff">{{ headline }}</text>
  <text x="60" y="160" font-family="sans-serif" font-size="26" fill="#9fc2e0">{{ subhead }}</text>
  {% for s in sections %}
  <g transform="translate(60, {{ 240 + loop.index0 * 190 }})">
    <text x="0" y="0" font-family="sans-serif" font-size="46" font-weight="bold"
          fill="#e0342d">{{ s.stat_value }}</text>
    <text x="0" y="38" font-family="sans-serif" font-size="24"
          fill="#ffffff">{{ s.stat_label }}</text>
    <text x="0" y="74" font-family="sans-serif" font-size="18"
          fill="#cfe0ee">{{ s.body }}</text>
    <text x="0" y="104" font-family="sans-serif" font-size="16"
          fill="#7fa6c4">{{ s.heading }}</text>
  </g>
  {% endfor %}
  <g transform="translate(60, {{ 260 + sections|length * 190 }})">
    {% for m in key_messages %}
    <text x="0" y="{{ loop.index0 * 36 }}" font-family="sans-serif" font-size="20"
          fill="#ffffff">&#8226; {{ m }}</text>
    {% endfor %}
  </g>
  <text x="60" y="1310" font-family="sans-serif" font-size="16"
        fill="#9fc2e0">{{ footer }}</text>
</svg>
"""


def render_svg(artefact: Any, path: Path) -> None:
    """Render the infographic spec to an SVG file at `path`."""
    import jinja2

    template = jinja2.Environment(autoescape=True, undefined=jinja2.StrictUndefined).from_string(
        _TEMPLATE
    )
    svg = template.render(
        headline=artefact.headline,
        subhead=artefact.subhead,
        sections=artefact.sections,
        key_messages=artefact.key_messages,
        footer=artefact.footer,
    )
    path.write_text(svg, encoding="utf-8")
