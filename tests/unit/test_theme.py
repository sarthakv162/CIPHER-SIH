"""Unit coverage for render/theme.py: loading, accessors, fallbacks, missing-theme error."""

from __future__ import annotations

from pathlib import Path

import pytest

from rupantar.core.errors import ConfigError
from rupantar.render.theme import Theme, hex_to_rgb, load_theme


def test_loads_ntro_formal() -> None:
    theme = load_theme("ntro-formal")
    assert theme.name == "ntro-formal"
    assert theme.colour("accent").startswith("#")
    assert theme.px("display") > theme.px("body")


def test_severity_colour_falls_back_to_accent() -> None:
    theme = load_theme("ntro-formal")
    assert theme.severity_colour("critical") == theme.palette.severity["critical"]
    assert theme.severity_colour("nonsense") == theme.colour("accent")


def test_unknown_colour_and_size_raise() -> None:
    theme = load_theme("ntro-formal")
    with pytest.raises(ConfigError):
        theme.colour("chartreuse")
    with pytest.raises(ConfigError):
        theme.px("gigantic")


def test_missing_theme_is_a_typed_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as excinfo:
        load_theme("no-such-theme", configs_dir=tmp_path)
    assert "no-such-theme" in str(excinfo.value)


def test_font_fallback_chain_returns_none_when_nothing_exists() -> None:
    theme = Theme.model_validate(
        {
            "name": "t",
            "palette": {
                "primary": "#000000",
                "accent": "#ff0000",
                "background": "#000000",
                "surface": "#111111",
                "text": "#ffffff",
                "text_muted": "#888888",
                "text_inverse": "#000000",
            },
            "type_scale": {
                "display": 100,
                "title": 50,
                "heading": 30,
                "body": 20,
                "caption": 16,
                "footer": 14,
            },
            "fonts": {"regular": ["/no/such/font.ttf"], "bold": []},
        }
    )
    assert theme.font_path("regular") is None
    assert theme.font_path("bold") is None


def test_hex_to_rgb_handles_short_and_long() -> None:
    assert hex_to_rgb("#fff") == (255, 255, 255)
    assert hex_to_rgb("#0b1f33") == (11, 31, 51)
    with pytest.raises(ConfigError):
        hex_to_rgb("#nothex")
