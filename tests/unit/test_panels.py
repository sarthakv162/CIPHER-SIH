"""Unit coverage for render/panels.py: every layout renders a valid 1280x720 PNG."""

from __future__ import annotations

from pathlib import Path

import pytest

from rupantar.render.panels import _LAYOUTS, render_panel
from rupantar.render.theme import load_theme

_THEME = load_theme("ntro-formal")


def _assert_panel(path: Path) -> None:
    from PIL import Image

    assert path.read_bytes().startswith(b"\x89PNG")
    assert path.stat().st_size > 1000
    with Image.open(path) as image:
        assert image.size == (1280, 720)


@pytest.mark.parametrize("layout", _LAYOUTS)
def test_every_layout_renders(layout: str, tmp_path: Path) -> None:
    target = tmp_path / f"{layout}.png"
    render_panel(
        target,
        layout=layout,
        title="A themed panel title that is fairly long to force wrapping",
        body_lines=["8 days", "to full containment across the affected estate"],
        scene_index=2,
        scene_count=6,
        footer="video_package · abcdef",
        theme=_THEME,
    )
    _assert_panel(target)


def test_unknown_layout_falls_back_to_statement(tmp_path: Path) -> None:
    target = tmp_path / "weird.png"
    render_panel(
        target,
        layout="totally-made-up",
        title="Fallback",
        body_lines=["body"],
        scene_index=1,
        scene_count=3,
        footer="f",
        theme=_THEME,
    )
    _assert_panel(target)


def test_background_and_scrim(tmp_path: Path) -> None:
    from PIL import Image

    bg = tmp_path / "bg.png"
    Image.new("RGB", (400, 300), (200, 120, 40)).save(bg)
    target = tmp_path / "scrimmed.png"
    render_panel(
        target,
        layout="statement",
        title="Over a photo",
        body_lines=["legible text over a scrim"],
        scene_index=1,
        scene_count=2,
        footer="f",
        theme=_THEME,
        background=bg,
        scrim=True,
    )
    _assert_panel(target)


def test_lower_third_with_severity_uses_theme_colour(tmp_path: Path) -> None:
    from PIL import Image

    target = tmp_path / "lt.png"
    render_panel(
        target,
        layout="statement",
        title="Advisory-style",
        body_lines=["body"],
        scene_index=1,
        scene_count=2,
        footer="f",
        theme=_THEME,
        lower_third=("Security Advisory", "critical"),
    )
    _assert_panel(target)
    crit = _THEME.severity_rgb("critical")
    with Image.open(target) as image:
        colours = {c for _, c in image.convert("RGB").getcolors(maxcolors=100000) or []}
    assert crit in colours


def test_missing_theme_fonts_still_produce_a_panel(tmp_path: Path) -> None:
    from rupantar.render.theme import Theme

    theme = Theme.model_validate(
        {
            "name": "nofont",
            "palette": _THEME.palette.model_dump(),
            "type_scale": _THEME.type_scale,
            "fonts": {"regular": ["/no/such/font.ttf"], "bold": ["/also/missing.ttf"]},
        }
    )
    assert theme.font_path("regular") is None
    target = tmp_path / "nofont.png"
    render_panel(
        target,
        layout="title_card",
        title="Falls back to the default font",
        body_lines=["still renders"],
        scene_index=1,
        scene_count=1,
        footer="f",
        theme=theme,
    )
    _assert_panel(target)
