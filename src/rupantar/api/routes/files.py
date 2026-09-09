"""Artefact file routes: list a job's output files, serve one, and read its provenance manifest.

Read-only: nothing here writes to disk, so INV-5 cannot be violated from this module.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from rupantar.api.app import get_config, get_store
from rupantar.api.paths import job_files, resolve_job_file
from rupantar.audit.provenance import manifest_path, read_manifest
from rupantar.core.config import AppConfig
from rupantar.core.errors import ReleaseError
from rupantar.core.schemas import Job
from rupantar.core.store import Store

router = APIRouter(tags=["artefacts"])

CONTENT_TYPES: dict[str, str] = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".json": "application/json",
    ".md": "text/markdown; charset=utf-8",
    ".mp4": "video/mp4",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".srt": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
    ".wav": "audio/wav",
}
DEFAULT_CONTENT_TYPE = "application/octet-stream"


class ArtefactFile(BaseModel):
    """One downloadable file a job wrote, with its size, format and manifest presence."""

    name: str
    size_bytes: int
    format: str
    content_type: str
    has_manifest: bool


def content_type_for(name: str) -> str:
    """The content type to serve `name` with, falling back to a binary download."""
    return CONTENT_TYPES.get(Path(name).suffix.lower(), DEFAULT_CONTENT_TYPE)


@router.get("/transforms/{transform_id}/jobs/{job_id}/files")
async def list_job_files(
    transform_id: str,
    job_id: str,
    store: Annotated[Store, Depends(get_store)],
    config: Annotated[AppConfig, Depends(get_config)],
) -> list[ArtefactFile]:
    """List the artefact files this job wrote, excluding the sibling provenance manifests."""
    job = await require_job(store, transform_id, job_id)
    return [_entry(path) for path in job_files(job_output_dir(config, job))]


@router.get("/transforms/{transform_id}/jobs/{job_id}/files/{filename}")
async def get_job_file(
    transform_id: str,
    job_id: str,
    filename: str,
    store: Annotated[Store, Depends(get_store)],
    config: Annotated[AppConfig, Depends(get_config)],
) -> FileResponse:
    """Serve one file from the job's output directory; anything outside it is a 404."""
    job = await require_job(store, transform_id, job_id)
    path = resolve_job_file(job_output_dir(config, job), filename)
    if path is None:
        raise HTTPException(
            status_code=404,
            detail=f"no artefact file {filename!r} in job {job_id!r}",
        )
    return FileResponse(
        path,
        media_type=content_type_for(path.name),
        headers={"content-disposition": f"inline; filename*=UTF-8''{quote(path.name)}"},
    )


@router.get("/transforms/{transform_id}/jobs/{job_id}/manifest")
async def get_job_manifest(
    transform_id: str,
    job_id: str,
    store: Annotated[Store, Depends(get_store)],
    config: Annotated[AppConfig, Depends(get_config)],
) -> dict[str, Any]:
    """The provenance manifest for the job's primary artefact, or 404 before it is written."""
    job = await require_job(store, transform_id, job_id)
    path = _primary_manifest(config, job)
    if path is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"job {job_id!r} has no provenance manifest yet; wait for the transform to "
                "finish before reading provenance"
            ),
        )
    try:
        return read_manifest(path)
    except ReleaseError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


async def require_job(store: Store, transform_id: str, job_id: str) -> Job:
    """Fetch the job, 404ing when the transform is unknown or the job is not part of it."""
    jobs = await store.list_jobs_for_transform(transform_id)
    if not jobs:
        raise HTTPException(status_code=404, detail=f"transform {transform_id!r} not found")
    for job in jobs:
        if job.id == job_id:
            return job
    raise HTTPException(
        status_code=404, detail=f"job {job_id!r} not found in transform {transform_id!r}"
    )


def job_output_dir(config: AppConfig, job: Job) -> Path:
    """Where this job's files live: beside its artefact, else the configured outputs directory."""
    if job.artefact_path:
        return Path(job.artefact_path).parent
    return config.db_path.parent / "outputs" / job.id


def _primary_manifest(config: AppConfig, job: Job) -> Path | None:
    """The manifest beside the job's primary artefact, resolved inside the job directory."""
    if not job.artefact_path:
        return None
    name = manifest_path(Path(job.artefact_path)).name
    return resolve_job_file(job_output_dir(config, job), name)


def _entry(path: Path) -> ArtefactFile:
    """Describe one artefact file for the listing."""
    return ArtefactFile(
        name=path.name,
        size_bytes=path.stat().st_size,
        format=path.suffix.lstrip(".").lower(),
        content_type=content_type_for(path.name),
        has_manifest=manifest_path(path).is_file(),
    )
