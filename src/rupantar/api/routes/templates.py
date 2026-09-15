"""GET /templates: the document templates a picker can offer, with thumbnail URLs.
GET /templates/{id}/thumbnail: the thumbnail image itself, served as a static file.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from rupantar.api.app import get_config
from rupantar.api.paths import safe_file_name
from rupantar.core.config import AppConfig
from rupantar.render.template_registry import (
    TemplateSpec,
    get_template,
    load_templates,
    template_file,
)

router = APIRouter(tags=["templates"])


class TemplateEntry(BaseModel):
    """One selectable output template."""

    id: str
    label: str
    description: str
    supports: list[str]
    thumbnail_url: str | None = None


@router.get("/templates")
async def list_templates(config: Annotated[AppConfig, Depends(get_config)]) -> list[TemplateEntry]:
    """List every template declared in configs/templates/templates.yaml."""
    entries = []
    for spec in load_templates(config.configs_dir):
        entries.append(
            TemplateEntry(
                id=spec.id,
                label=spec.label,
                description=spec.description.strip(),
                supports=list(spec.supports),
                thumbnail_url=_thumbnail_url(config, spec),
            )
        )
    return entries


def _thumbnail_url(config: AppConfig, spec: TemplateSpec) -> str | None:
    """The thumbnail route for `spec`, or None when it declares none or the file is missing."""
    if not spec.thumbnail or not safe_file_name(spec.thumbnail):
        return None
    if not template_file(config.configs_dir, spec.thumbnail).is_file():
        return None
    return f"/templates/{spec.id}/thumbnail"


@router.get("/templates/{template_id}/thumbnail")
async def template_thumbnail(
    template_id: str, config: Annotated[AppConfig, Depends(get_config)]
) -> FileResponse:
    """Serve one template's thumbnail PNG, or 404 when the template or its image is missing."""
    spec = get_template(template_id, configs_dir=config.configs_dir)
    if spec is None or not spec.thumbnail or not safe_file_name(spec.thumbnail):
        raise HTTPException(status_code=404, detail=f"template {template_id!r} has no thumbnail")
    path = template_file(config.configs_dir, spec.thumbnail)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"template {template_id!r} has no thumbnail")
    return FileResponse(path, media_type="image/png")
