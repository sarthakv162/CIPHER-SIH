"""Document-template manifest: real `.potx`/`.dotx` files that `render/pptx_render.py` and
`render/docx_render.py` load, declared in `configs/templates/templates.yaml`.

Not the same thing as `render/theme.py`'s video/SVG design-token themes -- a document
template here is a real Office file with its own slide layouts or named paragraph styles,
loaded through python-pptx/python-docx rather than drawn from a colour/type-scale YAML.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from rupantar.core.config import find_configs_dir
from rupantar.core.errors import ConfigError

DEFAULT_TEMPLATE = "ntro-formal"


class PptxBinding(BaseModel):
    """The `.potx` file backing this template and its `Slide.layout` -> layout-index map."""

    model_config = ConfigDict(extra="forbid")

    file: str
    layouts: dict[str, int] = Field(default_factory=dict)


class DocxBinding(BaseModel):
    """The `.dotx` file backing this template and its abstract-key -> named-style map."""

    model_config = ConfigDict(extra="forbid")

    file: str
    styles: dict[str, str] = Field(default_factory=dict)


class TemplateSpec(BaseModel):
    """One selectable output template."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    description: str = ""
    supports: list[str] = Field(default_factory=list)
    thumbnail: str | None = None
    pptx: PptxBinding | None = None
    docx: DocxBinding | None = None


def manifest_path(configs_dir: Path | None = None) -> Path:
    """Absolute path to `configs/templates/templates.yaml`."""
    base = configs_dir if configs_dir is not None else find_configs_dir()
    return base / "templates" / "templates.yaml"


_CACHE: dict[str, list[TemplateSpec]] = {}


def load_templates(configs_dir: Path | None = None) -> list[TemplateSpec]:
    """Every template declared in `templates.yaml`, in file order; `[]` if it does not exist."""
    cache_key = str(configs_dir) if configs_dir is not None else ""
    if configs_dir is None and cache_key in _CACHE:
        return _CACHE[cache_key]
    path = manifest_path(configs_dir)
    if not path.is_file():
        return []
    try:
        data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid templates manifest YAML: {exc}", path=str(path)) from exc
    if not isinstance(data, dict):
        raise ConfigError("templates manifest must be a mapping", path=str(path))
    specs = [TemplateSpec.model_validate(entry) for entry in data.get("templates", [])]
    if configs_dir is None:
        _CACHE[cache_key] = specs
    return specs


def get_template(template_id: str, *, configs_dir: Path | None = None) -> TemplateSpec | None:
    """The template with this id, or None when it is unknown or the manifest is unreadable."""
    try:
        templates = load_templates(configs_dir)
    except ConfigError:
        return None
    return next((t for t in templates if t.id == template_id), None)


def template_file(configs_dir: Path | None, file_name: str) -> Path:
    """Absolute path of one template asset (a `.potx`/`.dotx`/thumbnail) by its declared name."""
    base = configs_dir if configs_dir is not None else find_configs_dir()
    return base / "templates" / file_name
