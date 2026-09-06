"""GET /jobs/{job_id}: one artefact job within a Transform."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from rupantar.api.app import get_store
from rupantar.core.schemas import Job
from rupantar.core.store import Store

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, store: Annotated[Store, Depends(get_store)]) -> Job:
    """Return the job row, or 404 if the id is unknown."""
    job = await store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job {job_id!r} not found")
    return job
