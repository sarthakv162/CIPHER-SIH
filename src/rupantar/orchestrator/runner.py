"""Batch orchestration: one dossier, modality-grouped leases, one artefact file per job."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from rupantar.agents.base import ArtefactAgent
from rupantar.core.artefacts import ArtefactBase
from rupantar.core.errors import AgentError, ConfigError
from rupantar.core.schemas import (
    Job,
    JobStatus,
    SourceDossier,
    SourceInput,
    SourceKind,
    TextBlock,
    TransformRequest,
)
from rupantar.core.store import Store
from rupantar.models.client import LlamaClient
from rupantar.models.manager import ModelManager
from rupantar.orchestrator.planner import plan
from rupantar.orchestrator.scheduler import schedule


def _utcnow() -> datetime:
    """Timezone-aware present instant."""
    return datetime.now(UTC)


def _uuid() -> str:
    """A fresh hex identifier."""
    return uuid.uuid4().hex


async def prepare(
    request: TransformRequest,
    *,
    agents: Mapping[str, ArtefactAgent],
    store: Store,
    new_id: Callable[[], str] = _uuid,
    clock: Callable[[], datetime] = _utcnow,
) -> tuple[str, list[Job]]:
    """Plan the Transform, persist it plus every PENDING job and the dossier, return their ids."""
    jobs = plan(request, agents, new_id=new_id, clock=clock)
    dossier = _build_dossier(request.sources[0], clock=clock, new_id=new_id)
    transform_id = jobs[0].transform_id
    await store.create_transform(transform_id, request)
    for job in jobs:
        await store.create_job(job)
    await store.save_dossier(dossier)
    return transform_id, jobs


async def execute(
    transform_id: str,
    *,
    manager: ModelManager,
    agents: Mapping[str, ArtefactAgent],
    store: Store,
    out_root: Path,
    stream: bool = False,
    clock: Callable[[], datetime] = _utcnow,
) -> list[Job]:
    """Run every persisted job of a Transform under modality-grouped leases; return final jobs."""
    jobs = await store.list_jobs_for_transform(transform_id)
    request = await store.get_transform_request(transform_id)
    if not jobs or request is None:
        raise ConfigError(f"transform {transform_id!r} has no persisted jobs; call prepare() first")
    dossier_text = _build_dossier(request.sources[0], clock=clock, new_id=_uuid).to_prompt_text()

    for group in _consecutive_runs(schedule(jobs)):
        async with manager.acquire(group[0].model_key) as lease:
            client = LlamaClient(lease.endpoint)
            try:
                for job in group:
                    await _run_job(
                        job, agents, dossier_text, request, client, store, out_root, clock, stream
                    )
            finally:
                await client.aclose()
    return await store.list_jobs_for_transform(transform_id)


async def run_batch(
    request: TransformRequest,
    *,
    manager: ModelManager,
    agents: Mapping[str, ArtefactAgent],
    store: Store,
    out_root: Path,
    stream: bool = False,
    clock: Callable[[], datetime] = _utcnow,
    new_id: Callable[[], str] = _uuid,
) -> list[Job]:
    """Plan, persist, and execute every job in a Transform, returning them in planner order."""
    transform_id, _ = await prepare(request, agents=agents, store=store, new_id=new_id, clock=clock)
    return await execute(
        transform_id,
        manager=manager,
        agents=agents,
        store=store,
        out_root=out_root,
        stream=stream,
        clock=clock,
    )


async def run_single(
    request: TransformRequest,
    *,
    manager: ModelManager,
    agents: Mapping[str, ArtefactAgent],
    store: Store,
    out_root: Path,
    stream: bool = False,
    clock: Callable[[], datetime] = _utcnow,
    new_id: Callable[[], str] = _uuid,
) -> Job:
    """Run only the first requested output type; a thin wrapper over `run_batch`."""
    jobs = await run_batch(
        request,
        manager=manager,
        agents=agents,
        store=store,
        out_root=out_root,
        stream=stream,
        clock=clock,
        new_id=new_id,
    )
    return jobs[0]


def _consecutive_runs(jobs: list[Job]) -> list[list[Job]]:
    """Split an ordered job list into maximal runs sharing one model_key."""
    runs: list[list[Job]] = []
    for job in jobs:
        if runs and runs[-1][0].model_key == job.model_key:
            runs[-1].append(job)
        else:
            runs.append([job])
    return runs


async def _run_job(
    job: Job,
    agents: Mapping[str, ArtefactAgent],
    dossier_text: str,
    request: TransformRequest,
    client: LlamaClient,
    store: Store,
    out_root: Path,
    clock: Callable[[], datetime],
    stream: bool,
) -> None:
    """Generate one artefact, writing it and marking the job SUCCEEDED, or FAILED on AgentError."""
    agent = agents[job.artefact_type.value]
    await _transition(store, job, JobStatus.RUNNING, clock)
    try:
        artefact = await agent.run(dossier_text, request.params, client, stream=stream)
    except AgentError as exc:
        job.error = str(exc)
        await _transition(store, job, JobStatus.FAILED, clock)
        return
    job.artefact_path = _write_artefact(out_root / job.id, agent.artefact_type, artefact)
    await _transition(store, job, JobStatus.SUCCEEDED, clock)


async def _transition(
    store: Store, job: Job, status: JobStatus, clock: Callable[[], datetime]
) -> None:
    """Set the job status and timestamp and persist the row."""
    job.status = status
    job.updated_at = clock()
    await store.update_job(job)


def _write_artefact(out_dir: Path, artefact_type: str, artefact: ArtefactBase) -> str:
    """Write the validated artefact JSON (pretty) and return its path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{artefact_type}.json"
    path.write_text(artefact.model_dump_json(indent=2, by_alias=True), encoding="utf-8")
    return str(path)


def _build_dossier(
    source: SourceInput,
    *,
    clock: Callable[[], datetime],
    new_id: Callable[[], str],
) -> SourceDossier:
    """Assemble a minimal single-block dossier from one text or file source."""
    if source.kind is SourceKind.file:
        path = Path(source.path or "")
        if not path.is_file():
            raise ConfigError(f"source file not found: {path}", path=str(path))
        text = path.read_text(encoding="utf-8")
        name = path.name
    else:
        text = source.text or ""
        name = "inline"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return SourceDossier(
        id=new_id(),
        created_at=clock(),
        sha256=digest,
        text_blocks=[TextBlock(source_name=name, text=text)],
    )
