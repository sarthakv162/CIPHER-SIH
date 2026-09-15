"""Unit coverage for render/_video_svg.py: every layout renders a valid SVG-rasterised PNG,
and a forced resvg failure degrades to the Pillow panel renderer with a recorded warning.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from rupantar.core.artefacts import InfographicSpec
from rupantar.render._video_scene import PanelPlan, render_plan_panel
from rupantar.render._video_svg import _LAYOUTS, render_svg_panel
from rupantar.render.charts import ChartData
from rupantar.render.theme import load_theme

_THEME = load_theme("ntro-formal")
_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _assert_panel(path: Path) -> None:
    from PIL import Image

    assert path.read_bytes().startswith(b"\x89PNG")
    with Image.open(path) as image:
        assert image.size == (1280, 720)


@pytest.mark.parametrize("layout", _LAYOUTS)
def test_every_layout_renders(layout: str, tmp_path: Path) -> None:
    target = tmp_path / f"{layout}.png"
    render_svg_panel(
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
    render_svg_panel(
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


def test_background_scrim_and_lower_third_render(tmp_path: Path) -> None:
    from PIL import Image

    bg = tmp_path / "bg.png"
    Image.new("RGB", (400, 300), (200, 120, 40)).save(bg)
    target = tmp_path / "scrimmed.png"
    render_svg_panel(
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
        lower_third=("Video Package", "critical"),
    )
    _assert_panel(target)


def test_infographic_hero_uses_the_real_rendered_svg(tmp_path: Path) -> None:
    spec = InfographicSpec.model_validate_json(
        (_FIXTURES / "artefacts" / "infographic_spec.json").read_text()
    )
    target = tmp_path / "hero.png"
    render_svg_panel(
        target,
        layout="infographic_hero",
        title=spec.headline,
        body_lines=[spec.subhead],
        scene_index=1,
        scene_count=3,
        footer="f",
        theme=_THEME,
        hero_spec=spec,
    )
    _assert_panel(target)


def test_infographic_hero_without_a_spec_falls_back_to_a_text_layout(tmp_path: Path) -> None:
    target = tmp_path / "hero_no_spec.png"
    render_svg_panel(
        target,
        layout="infographic_hero",
        title="Key figures",
        body_lines=["subhead", "section one", "section two"],
        scene_index=1,
        scene_count=3,
        footer="f",
        theme=_THEME,
    )
    _assert_panel(target)


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
    target = tmp_path / "nofont.png"
    render_svg_panel(
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


def test_resvg_failure_degrades_to_the_pillow_panel_with_a_warning(tmp_path: Path) -> None:
    plan = PanelPlan(
        index=2, layout="statement", title="T", body_lines=["b"], duration=5, narration=""
    )
    warnings: list[str] = []
    target = tmp_path / "panel_02.png"
    with mock.patch("resvg_py.svg_to_bytes", side_effect=ValueError("boom")):
        render_plan_panel(target, plan, 4, "footer", _THEME, warnings)
    _assert_panel(target)
    assert any("svg render failed" in w and "fell back" in w for w in warnings)


def test_chart_layout_stays_on_the_pillow_path_unaffected(tmp_path: Path) -> None:
    data = ChartData(kind="bar", title="Key figures", points=[("a", 1.0), ("b", 2.0)])
    plan = PanelPlan(
        index=3,
        layout="chart",
        title="Key figures",
        body_lines=[],
        duration=5,
        narration="",
        chart_data=data,
    )
    warnings: list[str] = []
    target = tmp_path / "chart.png"
    with mock.patch("resvg_py.svg_to_bytes", side_effect=AssertionError("must not be called")):
        render_plan_panel(target, plan, 4, "footer", _THEME, warnings)
    _assert_panel(target)
    assert warnings == []
