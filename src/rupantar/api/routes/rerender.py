"""POST /transforms/{id}/jobs/{id}/render: regenerate a job's rendered files from its already
-generated artefact JSON, optionally with a different template. No model is acquired -- this
is pure, deterministic rendering over data already on disk, safe to repeat and safe to call
from the console's artefact viewer without ever touching ModelManager.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from rupantar.agents.base import ArtefactAgent
from rupantar.api.app import get_agents, get_config, get_store
from rupantar.audit.provenance import (
    Manifest,
    app_version,
    manifest_path,
    read_manifest,
    write_manifest,
)
from rupantar.core.artefacts import ARTEFACT_MODELS
from rupantar.core.config import AppConfig
from rupantar.core.errors import ReleaseError, RenderError
from rupantar.core.schemas import Job, JobStatus
from rupantar.core.store import Store
from rupantar.orchestrator.runner import resolve_operator
from rupantar.render.base import FORMATS, render
from rupantar.render.context import RenderContext
from rupantar.render.template_registry import DEFAULT_TEMPLATE

router = APIRouter(tags=["render"])


class RerenderResult(BaseModel):
    """What changed on disk from one re-render call."""

    files: list[str]
    template: str
    warnings: list[str] = []


@router.post("/transforms/{transform_id}/jobs/{job_id}/render")
async def rerender_job(
    transform_id: str,
    job_id: str,
    store: Annotated[Store, Depends(get_store)],
    agents: Annotated[dict[str, ArtefactAgent], Depends(get_agents)],
    config: Annotated[AppConfig, Depends(get_config)],
    template: Annotated[str, Query()] = DEFAULT_TEMPLATE,
) -> RerenderResult:
    """Re-render one SUCCEEDED job's files from its stored artefact JSON under a new template."""
    job = await _find_job(store, transform_id, job_id)
    artefact_path, artefact = await _load_artefact(job)
    dossier = await store.get_dossier(transform_id)
    request = await store.get_transform_request(transform_id)

    context = RenderContext(dossier=dossier, template_id=template, configs_dir=config.configs_dir)
    try:
        rendered = render(
            artefact,
            artefact_path.parent,
            formats=FORMATS.get(job.artefact_type.value, ()),
            context=context,
        )
    except RenderError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    params = dict(request.params.model_dump(mode="json")) if request else {}
    params["template"] = template
    agent = agents.get(job.artefact_type.value)
    for path in rendered:
        _restamp_manifest(path, job=job, agent=agent, params=params, warnings=context.warnings)
    return RerenderResult(
        files=[p.name for p in rendered], template=template, warnings=context.warnings
    )


async def _find_job(store: Store, transform_id: str, job_id: str) -> Job:
    """The job, or a 404 if it does not exist or belongs to a different transform."""
    job = await store.get_job(job_id)
    if job is None or job.transform_id != transform_id:
        raise HTTPException(status_code=404, detail=f"job {job_id!r} not found")
    return job


async def _load_artefact(job: Job) -> tuple[Path, Any]:
    """The job's artefact JSON path and its validated model, or a 404/409 explaining why not."""
    if job.status is not JobStatus.SUCCEEDED or not job.artefact_path:
        raise HTTPException(status_code=409, detail=f"job {job.id!r} has no rendered artefact")
    path = Path(job.artefact_path)
    model = ARTEFACT_MODELS.get(job.artefact_type.value)
    if model is None or not path.is_file():
        raise HTTPException(status_code=404, detail="the artefact JSON is no longer on disk")
    return path, model.model_validate_json(path.read_text(encoding="utf-8"))


def _restamp_manifest(
    path: Path,
    *,
    job: Job,
    agent: ArtefactAgent | None,
    params: dict[str, Any],
    warnings: list[str],
) -> None:
    """Write a manifest for a re-rendered file, preserving verification/release from the old one."""
    existing: dict[str, Any] = {}
    old = manifest_path(path)
    if old.is_file():
        try:
            existing = read_manifest(old)
        except ReleaseError:
            existing = {}
    manifest = Manifest(
        source_sha256=existing.get("source_sha256", ""),
        artefact_type=job.artefact_type.value,
        artefact_format=path.suffix.lstrip("."),
        model_key=existing.get("model_key", job.model_key),
        model_sha256=existing.get("model_sha256"),
        model_quant=existing.get("model_quant", "unknown"),
        prompt_version=agent.prompt_version if agent else existing.get("prompt_version", "1"),
        generation_params=params,
        created_at=existing.get("created_at", job.created_at.isoformat()),
        rendered_at=datetime.now(UTC).isoformat(),
        operator=existing.get("operator", resolve_operator()),
        app_version=app_version(),
        job_id=job.id,
        transform_id=job.transform_id,
        verification=existing.get("verification"),
        release=existing.get("release"),
        render_warnings=warnings,
    )
    write_manifest(path, manifest)
