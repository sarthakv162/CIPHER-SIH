"""Transform routes: accept a batch, report aggregate status, list parsed artefacts."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from rupantar.agents.base import ArtefactAgent
from rupantar.api.app import get_agents, get_config, get_manager, get_store
from rupantar.core.config import AppConfig
from rupantar.core.errors import ConfigError
from rupantar.core.schemas import Job, JobStatus, TransformRequest
from rupantar.core.store import Store
from rupantar.models.manager import ModelManager
from rupantar.orchestrator.runner import execute, prepare

router = APIRouter(tags=["transforms"])
_log = logging.getLogger("rupantar.api")


class JobRef(BaseModel):
    """A job id paired with the artefact type it will produce."""

    job_id: str
    artefact_type: str


class TransformAccepted(BaseModel):
    """202 response: the batch is persisted and execution has been scheduled."""

    transform_id: str
    status: str
    jobs: list[JobRef]


class TransformStatus(BaseModel):
    """Aggregate status of a Transform plus every job row."""

    transform_id: str
    status: str
    jobs: list[Job]


class ArtefactEntry(BaseModel):
    """One job's artefact: parsed JSON when SUCCEEDED, otherwise just its status."""

    job_id: str
    artefact_type: str
    status: str
    path: str | None = None
    artefact: dict[str, Any] | None = None


def _aggregate(jobs: list[Job]) -> str:
    """Fold job statuses into one batch status (RUNNING/PENDING/FAILED/SUCCEEDED)."""
    statuses = {job.status for job in jobs}
    if JobStatus.RUNNING in statuses:
        return "RUNNING"
    if JobStatus.PENDING in statuses:
        return "PENDING"
    if statuses == {JobStatus.SUCCEEDED}:
        return "SUCCEEDED"
    return "FAILED"


def _spawn_execution(request: Request, transform_id: str, out_root: Path) -> None:
    """Schedule execute() as a tracked background task so it is not garbage collected."""
    manager: ModelManager = request.app.state.manager
    store: Store = request.app.state.store
    agents: dict[str, ArtefactAgent] = request.app.state.agents
    tasks: set[asyncio.Task[Any]] = request.app.state.tasks

    strict = os.environ.get("RUPANTAR_STRICT_AIRGAP", "").lower() in ("1", "true", "yes")
    task = asyncio.create_task(
        execute(
            transform_id,
            manager=manager,
            agents=agents,
            store=store,
            out_root=out_root,
            strict_airgap=strict,
        )
    )
    tasks.add(task)

    def _done(finished: asyncio.Task[Any]) -> None:
        tasks.discard(finished)
        if not finished.cancelled() and finished.exception() is not None:
            _log.error("transform %s execution failed: %s", transform_id, finished.exception())

    task.add_done_callback(_done)


@router.post("/transforms", status_code=202)
async def create_transform(
    body: TransformRequest,
    request: Request,
    store: Annotated[Store, Depends(get_store)],
    agents: Annotated[dict[str, ArtefactAgent], Depends(get_agents)],
    config: Annotated[AppConfig, Depends(get_config)],
    _manager: Annotated[ModelManager, Depends(get_manager)],
) -> TransformAccepted:
    """Persist the batch and its PENDING jobs, then kick execution off in the background."""
    try:
        transform_id, jobs = await prepare(body, agents=agents, store=store)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _spawn_execution(request, transform_id, config.db_path.parent / "outputs")
    return TransformAccepted(
        transform_id=transform_id,
        status="accepted",
        jobs=[JobRef(job_id=job.id, artefact_type=job.artefact_type.value) for job in jobs],
    )


@router.get("/transforms/{transform_id}")
async def get_transform(
    transform_id: str, store: Annotated[Store, Depends(get_store)]
) -> TransformStatus:
    """Return the aggregate batch status and every job, or 404 if the id is unknown."""
    jobs = await store.list_jobs_for_transform(transform_id)
    if not jobs:
        raise HTTPException(status_code=404, detail=f"transform {transform_id!r} not found")
    return TransformStatus(transform_id=transform_id, status=_aggregate(jobs), jobs=jobs)


@router.get("/transforms/{transform_id}/artefacts")
async def get_transform_artefacts(
    transform_id: str, store: Annotated[Store, Depends(get_store)]
) -> list[ArtefactEntry]:
    """List one entry per job; SUCCEEDED jobs carry the parsed artefact JSON."""
    jobs = await store.list_jobs_for_transform(transform_id)
    if not jobs:
        raise HTTPException(status_code=404, detail=f"transform {transform_id!r} not found")
    return [await _artefact_entry(job) for job in jobs]


async def _artefact_entry(job: Job) -> ArtefactEntry:
    """Build one ArtefactEntry, reading and parsing the artefact file for SUCCEEDED jobs."""
    entry = ArtefactEntry(
        job_id=job.id, artefact_type=job.artefact_type.value, status=job.status.value
    )
    if job.status is JobStatus.SUCCEEDED and job.artefact_path:
        path = Path(job.artefact_path)
        entry.path = str(path)
        if path.is_file():
            text = await asyncio.to_thread(lambda: path.read_text(encoding="utf-8"))
            entry.artefact = json.loads(text)
    return entry
