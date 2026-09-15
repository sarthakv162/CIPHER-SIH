"""A hardcoded fallback theme, and a loader that never raises, shared by the pdf/docx/pptx
renderers so a missing or broken theme YAML degrades a document instead of crashing the job.
"""

from __future__ import annotations

from typing import Any

from rupantar.core.errors import ConfigError
from rupantar.render.context import RenderContext
from rupantar.render.theme import Theme, load_theme

_FALLBACK_THEME_DATA: dict[str, Any] = {
    "name": "renderer-fallback",
    "palette": {
        "primary": "#0b1f33",
        "accent": "#e0342d",
        "background": "#ffffff",
        "surface": "#12324f",
        "text": "#ffffff",
        "text_muted": "#5a5a5a",
        "text_inverse": "#0b1f33",
        "severity": {
            "low": "#2e7d32",
            "medium": "#f4b400",
            "high": "#ef6c00",
            "critical": "#c62828",
        },
    },
    "type_scale": {
        "display": 132,
        "title": 58,
        "heading": 34,
        "body": 24,
        "caption": 18,
        "footer": 16,
    },
}

FALLBACK_THEME = Theme.model_validate(_FALLBACK_THEME_DATA)


def warn(context: RenderContext | None, message: str) -> None:
    """Record a degradation warning on the shared context, if one was given."""
    if context is not None:
        context.warnings.append(message)


def safe_theme(context: RenderContext | None) -> Theme:
    """Load the requested theme; any `ConfigError` degrades to the built-in fallback palette."""
    name = context.theme_name if context is not None else "ntro-formal"
    configs_dir = context.configs_dir if context is not None else None
    try:
        return load_theme(name, configs_dir=configs_dir)
    except ConfigError as exc:
        warn(context, f"theme {name!r} could not be loaded ({exc}); using a fallback palette")
        return FALLBACK_THEME
