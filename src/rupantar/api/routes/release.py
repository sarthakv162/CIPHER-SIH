"""POST /transforms/{id}/jobs/{id}/release: operator acknowledgement of a verification finding."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from rupantar.api.app import get_store
from rupantar.audit.provenance import Release, is_manifest, record_release
from rupantar.core.errors import ReleaseError
from rupantar.core.schemas import Job
from rupantar.core.store import Store
from rupantar.verify.report import VerificationReport

router = APIRouter(tags=["oversight"])


class ReleaseRequest(BaseModel):
    """Who is releasing the artefact and which findings they have acknowledged."""

    operator: str = Field(min_length=1)
    acknowledged_claim_ids: list[str] = Field(default_factory=list)
    acknowledged_relations: list[str] = Field(default_factory=list)
    note: str = ""


class ReleaseResult(BaseModel):
    """The recorded acknowledgement and every manifest it was stamped into."""

    transform_id: str
    job_id: str
    released_by: str
    released_at: str
    manifests: list[str]


@router.get("/transforms/{transform_id}/verification")
async def get_verification(
    transform_id: str, store: Annotated[Store, Depends(get_store)]
) -> VerificationReport:
    """The full report: every claim with its status and evidence, plus every relation.

    `GET /transforms/{id}` carries only the counts. The oversight workflow needs the
    claims and the CONFLICT relations themselves to show what actually disagrees.
    """
    jobs = await store.list_jobs_for_transform(transform_id)
    if not jobs:
        raise HTTPException(status_code=404, detail=f"transform {transform_id!r} not found")
    report = await store.get_verification_report(transform_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"transform {transform_id!r} has no verification report yet",
        )
    return report


@router.post("/transforms/{transform_id}/jobs/{job_id}/release")
async def release_job(
    transform_id: str,
    job_id: str,
    body: ReleaseRequest,
    store: Annotated[Store, Depends(get_store)],
) -> ReleaseResult:
    """Stamp the operator acknowledgement into every manifest this job produced."""
    job = await _require_job(store, transform_id, job_id)
    release = Release(
        released_by=body.operator,
        released_at=datetime.now(UTC).isoformat(),
        acknowledged_claim_ids=body.acknowledged_claim_ids,
        acknowledged_relations=body.acknowledged_relations,
        note=body.note,
    )
    manifests = _job_manifests(job)
    if not manifests:
        raise HTTPException(
            status_code=409,
            detail=(
                f"job {job_id!r} has no artefact manifest to stamp; only a SUCCEEDED job that "
                "wrote files can be released"
            ),
        )
    try:
        for manifest in manifests:
            record_release(manifest, release)
    except ReleaseError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReleaseResult(
        transform_id=transform_id,
        job_id=job_id,
        released_by=release.released_by,
        released_at=release.released_at,
        manifests=[str(path) for path in manifests],
    )


async def _require_job(store: Store, transform_id: str, job_id: str) -> Job:
    """Fetch the job, 404ing when either the transform or the job is unknown to this transform."""
    jobs = await store.list_jobs_for_transform(transform_id)
    if not jobs:
        raise HTTPException(status_code=404, detail=f"transform {transform_id!r} not found")
    for job in jobs:
        if job.id == job_id:
            return job
    raise HTTPException(
        status_code=404, detail=f"job {job_id!r} not found in transform {transform_id!r}"
    )


def _job_manifests(job: Job) -> list[Path]:
    """Every sibling manifest beside the artefact files this job wrote."""
    if not job.artefact_path:
        return []
    job_dir = Path(job.artefact_path).parent
    if not job_dir.is_dir():
        return []
    return sorted(path for path in job_dir.iterdir() if path.is_file() and is_manifest(path))
