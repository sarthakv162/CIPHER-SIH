"""Theme: the single source of visual identity for the renderers.

A theme is one YAML file under ``configs/templates/``. ``load_theme("<name>")`` reads
``configs/templates/<name>.yaml``; a second theme drops in with zero code change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from rupantar.core.config import find_configs_dir
from rupantar.core.errors import ConfigError

RGB = tuple[int, int, int]


class Palette(BaseModel):
    """Named colours plus a severity map, all ``#rrggbb`` strings."""

    model_config = ConfigDict(extra="forbid")

    primary: str
    accent: str
    background: str
    surface: str
    text: str
    text_muted: str
    text_inverse: str
    severity: dict[str, str] = Field(default_factory=dict)


class Spacing(BaseModel):
    """Base spacing unit plus a scale of named steps."""

    model_config = ConfigDict(extra="forbid")

    unit: int = 8
    steps: list[int] = Field(default_factory=list)


class Fonts(BaseModel):
    """Ordered candidate font-file paths for the regular and bold weights."""

    model_config = ConfigDict(extra="forbid")

    regular: list[str] = Field(default_factory=list)
    bold: list[str] = Field(default_factory=list)


class Wordmark(BaseModel):
    """Footer wordmark text and an optional (possibly empty) logo path."""

    model_config = ConfigDict(extra="forbid")

    text: str = ""
    logo_path: str = ""


class Theme(BaseModel):
    """Resolved visual identity with typed accessors the renderers need."""

    model_config = ConfigDict(extra="forbid")

    name: str
    palette: Palette
    type_scale: dict[str, int]
    spacing: Spacing = Field(default_factory=Spacing)
    fonts: Fonts = Field(default_factory=Fonts)
    wordmark: Wordmark = Field(default_factory=Wordmark)

    def colour(self, name: str) -> str:
        """Palette colour hex by name; raises ``ConfigError`` for an unknown key."""
        try:
            value = getattr(self.palette, name)
        except AttributeError as exc:
            raise ConfigError(
                f"theme {self.name!r} palette has no colour {name!r}", key=name
            ) from exc
        if not isinstance(value, str):
            raise ConfigError(f"theme {self.name!r} colour {name!r} is not a hex string", key=name)
        return value

    def severity_colour(self, level: str) -> str:
        """Severity tint hex, falling back to the accent colour for an unknown level."""
        return self.palette.severity.get(level.lower().strip(), self.palette.accent)

    def px(self, scale: str) -> int:
        """Pixel size for a named type-scale step; raises ``ConfigError`` for an unknown name."""
        try:
            return int(self.type_scale[scale])
        except KeyError as exc:
            raise ConfigError(
                f"theme {self.name!r} type_scale has no size {scale!r}", key=scale
            ) from exc

    def step(self, index: int) -> int:
        """A spacing step by index, clamped to the available scale (or a unit multiple)."""
        if self.spacing.steps:
            clamped = max(0, min(index, len(self.spacing.steps) - 1))
            return self.spacing.steps[clamped]
        return self.spacing.unit * max(1, index)

    def rgb(self, name: str) -> RGB:
        """Palette colour as an ``(r, g, b)`` tuple for Pillow."""
        return hex_to_rgb(self.colour(name))

    def severity_rgb(self, level: str) -> RGB:
        """Severity tint as an ``(r, g, b)`` tuple for Pillow."""
        return hex_to_rgb(self.severity_colour(level))

    def font_path(self, weight: str = "regular") -> str | None:
        """First existing font file for the weight, else ``None`` (caller uses the bitmap font)."""
        candidates = self.fonts.bold if weight == "bold" else self.fonts.regular
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                return candidate
        return None


def hex_to_rgb(value: str) -> RGB:
    """Convert ``#rrggbb`` or ``#rgb`` to an ``(r, g, b)`` tuple."""
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(char * 2 for char in text)
    if len(text) != 6:
        raise ConfigError(f"invalid hex colour {value!r}", key="palette")
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError as exc:
        raise ConfigError(f"invalid hex colour {value!r}", key="palette") from exc


def theme_path(name: str, configs_dir: Path | None = None) -> Path:
    """Absolute path to a theme YAML under ``configs/templates/``."""
    base = configs_dir if configs_dir is not None else find_configs_dir()
    return base / "templates" / f"{name}.yaml"


_CACHE: dict[str, Theme] = {}


def load_theme(name: str = "ntro-formal", *, configs_dir: Path | None = None) -> Theme:
    """Load and validate the named theme; results are memoised per name."""
    if configs_dir is None and name in _CACHE:
        return _CACHE[name]
    path = theme_path(name, configs_dir)
    if not path.is_file():
        raise ConfigError(
            f"theme {name!r} not found; create {path} or pass an existing theme name",
            path=str(path),
        )
    try:
        data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid theme YAML: {exc}", path=str(path)) from exc
    if not isinstance(data, dict):
        raise ConfigError("theme file must be a mapping", path=str(path))
    theme = Theme.model_validate(data)
    if configs_dir is None:
        _CACHE[name] = theme
    return theme
