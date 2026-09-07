"""Theme-driven 1280x720 panel rendering with Pillow (imported inside functions, INV-3).

Every panel carries a title, a themed heading rule, layout-specific body content, a
``SCENE n / N`` indicator, and a persistent footer (artefact id + wordmark). A failure in
any single panel is the caller's to catch -- these helpers may raise, ``render_panel`` does
its own best-effort degradation but the batch caller still wraps it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rupantar.render.theme import RGB, Theme

CANVAS = (1280, 720)
MARGIN = 64
_LAYOUTS = (
    "title_card",
    "statement",
    "stat_block",
    "quote",
    "closing",
    "infographic_hero",
    "chart",
)


def render_panel(
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
) -> None:
    """Render one panel PNG for ``layout`` to ``target``."""
    from PIL import Image, ImageDraw

    chosen = layout if layout in _LAYOUTS else "statement"
    image = _canvas(theme, background, scrim or background is not None)
    draw = ImageDraw.Draw(image)
    centered = chosen in ("title_card", "closing")
    top = _draw_title(draw, theme, title, centered=centered)
    _BODY[chosen](draw, theme, [line for line in body_lines if line], top, image)
    _draw_indicator(draw, theme, scene_index, scene_count)
    if lower_third is not None:
        _draw_lower_third(image, draw, theme, lower_third)
    _draw_footer(draw, theme, footer)
    image.save(target, format="PNG")
    if isinstance(image, Image.Image):
        image.close()


def _canvas(theme: Theme, background: Path | None, scrim: bool) -> Any:
    """A background-filled canvas: cover-fit source image with an optional scrim, else flat."""
    from PIL import Image

    base = Image.new("RGB", CANVAS, theme.rgb("background"))
    if background is not None and Path(background).is_file():
        try:
            with Image.open(background) as src:
                base = _cover_fit(src.convert("RGB"))
        except Exception:  # noqa: BLE001 - a corrupt source falls back to the flat theme fill
            base = Image.new("RGB", CANVAS, theme.rgb("background"))
    if scrim:
        wash = tuple(int(channel * 0.35) for channel in theme.rgb("primary"))
        overlay = Image.new("RGBA", CANVAS, (*wash, 205))
        base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    return base


def _cover_fit(src: Any) -> Any:
    """Scale ``src`` to fully cover the canvas and centre-crop the overflow."""
    canvas_w, canvas_h = CANVAS
    scale = max(canvas_w / src.width, canvas_h / src.height)
    resized = src.resize((max(1, round(src.width * scale)), max(1, round(src.height * scale))))
    left = (resized.width - canvas_w) // 2
    top = (resized.height - canvas_h) // 2
    return resized.crop((left, top, left + canvas_w, top + canvas_h))


def _font(theme: Theme, weight: str, size: int) -> Any:
    """A truetype font from the theme's candidate chain, else the Pillow bitmap font."""
    from PIL import ImageFont

    path = theme.font_path(weight)
    if path is not None:
        for index in (0, None):
            try:
                if index is None:
                    return ImageFont.truetype(path, size)
                return ImageFont.truetype(path, size, index=index)
            except Exception:  # noqa: BLE001 - try the next candidate / fall through
                continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:  # noqa: BLE001 - any font failure drops to the bare bitmap font
        return ImageFont.load_default()


def _wrap(draw: Any, text: str, font: Any, max_width: int) -> list[str]:
    """Greedy pixel-width word wrap; never returns an empty list."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if current and draw.textlength(trial, font=font) > max_width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines or [""]


def _draw_title(draw: Any, theme: Theme, title: str, *, centered: bool) -> int:
    """Draw the title and its accent heading rule; return the y where the body may start."""
    font = _font(theme, "bold", theme.px("title"))
    text = title.strip() or "Untitled"
    lines = _wrap(draw, text, font, CANVAS[0] - 2 * MARGIN)[:3]
    y = MARGIN + 12
    for line in lines:
        x = _centre_x(draw, line, font) if centered else MARGIN
        draw.text((x, y), line, font=font, fill=theme.rgb("text"))
        y += int(theme.px("title") * 1.2)
    rule_y = y + 10
    rule_x0 = (CANVAS[0] - 220) // 2 if centered else MARGIN
    draw.rectangle((rule_x0, rule_y, rule_x0 + 220, rule_y + 6), fill=theme.rgb("accent"))
    return rule_y + 34


def _centre_x(draw: Any, text: str, font: Any) -> int:
    """The x that centres ``text`` on the canvas."""
    return int((CANVAS[0] - draw.textlength(text, font=font)) / 2)


def _body_lines(
    draw: Any, theme: Theme, lines: list[str], top: int, _image: Any, *, size: str = "body"
) -> None:
    """Left-aligned wrapped body paragraph in the muted body colour."""
    font = _font(theme, "regular", theme.px(size))
    y = top
    leading = int(theme.px(size) * 1.45)
    for raw in lines or [""]:
        for line in _wrap(draw, raw, font, CANVAS[0] - 2 * MARGIN):
            if y > CANVAS[1] - 150:
                return
            draw.text((MARGIN, y), line, font=font, fill=theme.rgb("text"))
            y += leading


def _body_statement(draw: Any, theme: Theme, lines: list[str], top: int, image: Any) -> None:
    """A statement panel: one emphatic wrapped sentence in heading size."""
    _body_lines(draw, theme, lines, top, image, size="heading")


def _body_centered(draw: Any, theme: Theme, lines: list[str], top: int, _image: Any) -> None:
    """Title-card / closing body: centred logline or call-to-action emphasis."""
    font = _font(theme, "regular", theme.px("heading"))
    wrapped: list[str] = []
    for raw in lines or [""]:
        wrapped += _wrap(draw, raw, font, CANVAS[0] - 3 * MARGIN)
    y = max(top, (CANVAS[1] - len(wrapped) * int(theme.px("heading") * 1.4)) // 2)
    for line in wrapped:
        draw.text((_centre_x(draw, line, font), y), line, font=font, fill=theme.rgb("text_muted"))
        y += int(theme.px("heading") * 1.4)


def _body_stat(draw: Any, theme: Theme, lines: list[str], top: int, _image: Any) -> None:
    """A stat block: an oversized figure with a label beneath it."""
    figure = lines[0] if lines else "--"
    label_lines = lines[1:] or (lines[:1] if len(lines) == 1 else ["figure"])
    fig_font = _font(theme, "bold", theme.px("display"))
    draw.text((MARGIN, top + 20), figure[:12], font=fig_font, fill=theme.rgb("accent"))
    label_font = _font(theme, "regular", theme.px("heading"))
    y = top + 40 + theme.px("display")
    for raw in label_lines:
        for line in _wrap(draw, raw, label_font, CANVAS[0] - 2 * MARGIN):
            draw.text((MARGIN, y), line, font=label_font, fill=theme.rgb("text"))
            y += int(theme.px("heading") * 1.3)


def _body_quote(draw: Any, theme: Theme, lines: list[str], top: int, _image: Any) -> None:
    """An oversized quotation treatment with a large opening quote mark."""
    mark_font = _font(theme, "bold", theme.px("display"))
    draw.text((MARGIN - 8, top - 20), "“", font=mark_font, fill=theme.rgb("accent"))
    quote_font = _font(theme, "bold", theme.px("heading"))
    y = top + 90
    body = " ".join(lines).strip('"“”')
    for line in _wrap(draw, body, quote_font, CANVAS[0] - 2 * MARGIN - 40)[:6]:
        draw.text((MARGIN + 24, y), line, font=quote_font, fill=theme.rgb("text"))
        y += int(theme.px("heading") * 1.4)


def _body_hero(draw: Any, theme: Theme, lines: list[str], top: int, _image: Any) -> None:
    """Infographic hero: the subhead then bulleted section labels, stacked without overlap."""
    sub_font = _font(theme, "regular", theme.px("heading"))
    y = top
    for raw in lines[:1]:
        for line in _wrap(draw, raw, sub_font, CANVAS[0] - 2 * MARGIN):
            draw.text((MARGIN, y), line, font=sub_font, fill=theme.rgb("text"))
            y += int(theme.px("heading") * 1.35)
    y += theme.step(3)
    font = _font(theme, "regular", theme.px("body"))
    for raw in lines[1:8]:
        for line in _wrap(draw, f"• {raw}", font, CANVAS[0] - 2 * MARGIN):
            if y > CANVAS[1] - 150:
                return
            draw.text((MARGIN, y), line, font=font, fill=theme.rgb("text_muted"))
            y += int(theme.px("body") * 1.5)


_BODY = {
    "title_card": _body_centered,
    "closing": _body_centered,
    "statement": _body_statement,
    "stat_block": _body_stat,
    "quote": _body_quote,
    "infographic_hero": _body_hero,
    "chart": _body_lines,
}


def _draw_indicator(draw: Any, theme: Theme, index: int, count: int) -> None:
    """Draw the ``SCENE n / N`` marker in the top-right corner."""
    font = _font(theme, "regular", theme.px("caption"))
    text = f"SCENE {index} / {count}" if count else f"SCENE {index}"
    draw.text(
        (CANVAS[0] - MARGIN - draw.textlength(text, font=font), MARGIN - 24),
        text,
        font=font,
        fill=theme.rgb("text_muted"),
    )


def _draw_lower_third(image: Any, draw: Any, theme: Theme, lower_third: tuple[str, str]) -> None:
    """Draw a persistent lower-third bar; a severity string tints its chip."""
    label, severity = lower_third
    bar_top = CANVAS[1] - 96
    draw.rectangle((0, bar_top, CANVAS[0], bar_top + 52), fill=theme.rgb("surface"))
    draw.rectangle((0, bar_top, 8, bar_top + 52), fill=theme.rgb("accent"))
    font = _font(theme, "bold", theme.px("caption"))
    draw.text((MARGIN, bar_top + 15), label.upper()[:60], font=font, fill=theme.rgb("text"))
    if severity.strip():
        chip: RGB = theme.severity_rgb(severity)
        text = severity.upper()[:12]
        width = int(draw.textlength(text, font=font)) + 28
        x0 = CANVAS[0] - MARGIN - width
        draw.rectangle((x0, bar_top + 10, x0 + width, bar_top + 42), fill=chip)
        draw.text((x0 + 14, bar_top + 15), text, font=font, fill=theme.rgb("text_inverse"))


def _draw_footer(draw: Any, theme: Theme, footer: str) -> None:
    """Draw the persistent footer: artefact id at left, wordmark at right."""
    font = _font(theme, "regular", theme.px("footer"))
    y = CANVAS[1] - 34
    draw.text((MARGIN, y), footer[:80], font=font, fill=theme.rgb("text_muted"))
    mark = theme.wordmark.text
    if mark:
        draw.text(
            (CANVAS[0] - MARGIN - draw.textlength(mark, font=font), y),
            mark,
            font=font,
            fill=theme.rgb("text_muted"),
        )
