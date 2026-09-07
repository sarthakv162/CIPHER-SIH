"""Pillow-drawn data charts (no matplotlib). Numbers are extracted only when genuinely
present in an ``InfographicSpec``; nothing is ever synthesised. ``PIL`` is imported inside
the drawing functions (INV-3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rupantar.render.panels import CANVAS, MARGIN, _font
from rupantar.render.theme import Theme

_LEADING_NUMBER = re.compile(r"^\s*([+-]?\d[\d,]*(?:\.\d+)?)")


@dataclass
class ChartData:
    """A parsed, ready-to-draw chart: a bar series or an ordered timeline of labels."""

    kind: str
    title: str
    points: list[tuple[str, float]] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)


def parse_leading_number(value: str) -> float | None:
    """Return the leading numeric value of a string (``"8 days"`` -> 8.0), else ``None``."""
    match = _LEADING_NUMBER.match(value or "")
    if match is None:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def extract_chart_data(spec: Any) -> ChartData | None:
    """Bar data from >=2 parseable section stat values, else a timeline, else ``None``."""
    sections = list(getattr(spec, "sections", []))
    points: list[tuple[str, float]] = []
    for section in sections:
        parsed = parse_leading_number(getattr(section, "stat_value", ""))
        if parsed is not None:
            points.append((str(getattr(section, "stat_label", "")).strip() or "value", parsed))
    if len(points) >= 2:
        return ChartData(kind="bar", title=str(getattr(spec, "headline", "")), points=points)
    layout = getattr(getattr(spec, "layout_recommendation", None), "value", None)
    if layout == "timeline" and len(sections) >= 2:
        labels = [str(getattr(s, "stat_label", "")).strip() or "step" for s in sections]
        return ChartData(kind="timeline", title=str(getattr(spec, "headline", "")), labels=labels)
    return None


def render_chart(target: Path, data: ChartData, theme: Theme) -> None:
    """Render ``data`` as a themed 1280x720 PNG (bar or timeline)."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", CANVAS, theme.rgb("background"))
    draw = ImageDraw.Draw(image)
    title_font = _font(theme, "bold", theme.px("heading"))
    draw.text(
        (MARGIN, MARGIN - 12), data.title[:60] or "Data", font=title_font, fill=theme.rgb("text")
    )
    draw.rectangle((MARGIN, MARGIN + 44, MARGIN + 200, MARGIN + 50), fill=theme.rgb("accent"))
    if data.kind == "timeline":
        _draw_timeline(draw, theme, data.labels)
    else:
        _draw_bars(draw, theme, data.points)
    image.save(target, format="PNG")
    image.close()


def _draw_bars(draw: Any, theme: Theme, points: list[tuple[str, float]]) -> None:
    """Horizontal bars scaled to the largest absolute value."""
    label_font = _font(theme, "regular", theme.px("caption"))
    top, bottom = MARGIN + 90, CANVAS[1] - 120
    peak = max((abs(value) for _, value in points), default=1.0) or 1.0
    slot = (bottom - top) / max(1, len(points))
    bar_h = min(56, slot * 0.6)
    axis_x = MARGIN + 260
    for index, (label, value) in enumerate(points):
        y = top + slot * index + (slot - bar_h) / 2
        width = (CANVAS[0] - axis_x - MARGIN) * (abs(value) / peak)
        draw.text(
            (MARGIN, y + bar_h / 2 - 10), label[:26], font=label_font, fill=theme.rgb("text_muted")
        )
        draw.rectangle((axis_x, y, axis_x + max(2, width), y + bar_h), fill=theme.rgb("accent"))
        figure = f"{value:g}"
        draw.text(
            (axis_x + max(2, width) + 10, y + bar_h / 2 - 10),
            figure,
            font=label_font,
            fill=theme.rgb("text"),
        )


def _draw_timeline(draw: Any, theme: Theme, labels: list[str]) -> None:
    """A single horizontal strip with evenly spaced, numbered nodes."""
    label_font = _font(theme, "regular", theme.px("caption"))
    mid = CANVAS[1] // 2
    left, right = MARGIN + 20, CANVAS[0] - MARGIN - 20
    draw.rectangle((left, mid - 3, right, mid + 3), fill=theme.rgb("surface"))
    count = max(1, len(labels))
    step = (right - left) / max(1, count - 1) if count > 1 else 0
    for index, label in enumerate(labels):
        cx = int(left + step * index) if count > 1 else (left + right) // 2
        draw.ellipse((cx - 12, mid - 12, cx + 12, mid + 12), fill=theme.rgb("accent"))
        for offset, line in enumerate(_wrap_label(label)):
            draw.text(
                (cx - 60, mid + 28 + offset * 22),
                line,
                font=label_font,
                fill=theme.rgb("text_muted"),
            )


def _wrap_label(label: str) -> list[str]:
    """Split a node label into at most two short lines."""
    words = label.split()
    if len(words) <= 2:
        return [label[:22]]
    half = len(words) // 2
    return [" ".join(words[:half])[:22], " ".join(words[half:])[:22]]
