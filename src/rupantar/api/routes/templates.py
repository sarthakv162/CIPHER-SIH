"""GET /templates: the output templates a picker can offer. No generation parameter is wired yet."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from rupantar.api.app import get_config
from rupantar.core.config import AppConfig
from rupantar.core.errors import ConfigError

router = APIRouter(tags=["templates"])
_log = logging.getLogger("rupantar.api")


class TemplateEntry(BaseModel):
    """One selectable output template."""

    name: str
    label: str
    description: str
    accent: str


def templates_dir(config: AppConfig) -> Path:
    """Where theme YAML files live."""
    return config.configs_dir / "templates"


@router.get("/templates")
async def list_templates(config: Annotated[AppConfig, Depends(get_config)]) -> list[TemplateEntry]:
    """List every readable template under configs/templates, sorted by name."""
    return read_templates(templates_dir(config))


def read_templates(directory: Path) -> list[TemplateEntry]:
    """Parse each `*.yaml` in `directory` into a TemplateEntry, skipping unreadable ones."""
    if not directory.is_dir():
        return []
    entries: list[TemplateEntry] = []
    for path in sorted(directory.glob("*.yaml")):
        entry = _entry(path)
        if entry is not None:
            entries.append(entry)
    return entries


def _entry(path: Path) -> TemplateEntry | None:
    """Load one theme file into a TemplateEntry, or None when it does not parse."""
    from rupantar.render.theme import load_theme

    try:
        theme = load_theme(path.stem, configs_dir=path.parent.parent)
    except ConfigError as exc:
        _log.warning("skipping template %s: %s", path.name, exc)
        return None
    return TemplateEntry(
        name=theme.name,
        label=theme.label or theme.name,
        description=theme.description.strip(),
        accent=theme.palette.accent,
    )
