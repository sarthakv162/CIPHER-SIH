"""Batch orchestration: one dossier, modality-grouped leases, one artefact file per job."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from rupantar import __version__
from rupantar.agents.base import ArtefactAgent
from rupantar.audit.provenance import Manifest, write_manifest
from rupantar.core.artefacts import ArtefactBase
from rupantar.core.errors import AgentError, ConfigError
from rupantar.core.schemas import (
    Job,
    JobStatus,
    SourceDossier,
    SourceInput,
    SourceKind,
    TransformRequest,
)
from rupantar.core.store import Store
from rupantar.ingest.dossier import assemble_dossier
from rupantar.models.client import LlamaClient
from rupantar.models.manager import ModelManager
from rupantar.orchestrator.planner import plan
from rupantar.orchestrator.scheduler import schedule
from rupantar.render.base import FORMATS, render

_DEFAULT_OPERATOR = "operator"


def _utcnow() -> datetime:
    """Timezone-aware present instant."""
    return datetime.now(UTC)


def _uuid() -> str:
    """A fresh hex identifier."""
    return uuid.uuid4().hex


@dataclass(frozen=True)
class _RunContext:
    """Everything a single job needs beyond its own row and the model client."""

    agents: Mapping[str, ArtefactAgent]
    dossier_text: str
    dossier_sha: str
    request: TransformRequest
    store: Store
    out_root: Path
    manager: ModelManager
    operator: str
    clock: Callable[[], datetime]
    stream: bool


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
    transform_id = jobs[0].transform_id
    _validate_sources(request.sources)
    await store.create_transform(transform_id, request)
    for job in jobs:
        await store.create_job(job)
    await store.save_dossier(SourceDossier(id=transform_id, created_at=clock(), sha256=""))
    return transform_id, jobs


async def execute(
    transform_id: str,
    *,
    manager: ModelManager,
    agents: Mapping[str, ArtefactAgent],
    store: Store,
    out_root: Path,
    stream: bool = False,
    operator: str = _DEFAULT_OPERATOR,
    clock: Callable[[], datetime] = _utcnow,
) -> list[Job]:
    """Run every persisted job of a Transform under modality-grouped leases; return final jobs."""
    jobs = await store.list_jobs_for_transform(transform_id)
    request = await store.get_transform_request(transform_id)
    if not jobs or request is None:
        raise ConfigError(f"transform {transform_id!r} has no persisted jobs; call prepare() first")
    dossier, _warnings = await assemble_dossier(
        request.sources,
        manager=manager,
        out_dir=out_root / transform_id / "_ingest",
        new_id=lambda: transform_id,
        clock=clock,
        language=request.params.language,
    )
    await store.save_dossier(dossier)
    ctx = _RunContext(
        agents=agents,
        dossier_text=dossier.to_prompt_text(),
        dossier_sha=dossier.sha256,
        request=request,
        store=store,
        out_root=out_root,
        manager=manager,
        operator=operator,
        clock=clock,
        stream=stream,
    )

    for group in _consecutive_runs(schedule(jobs)):
        async with manager.acquire(group[0].model_key) as lease:
            client = LlamaClient(lease.endpoint)
            try:
                for job in group:
                    await _run_job(job, ctx, client)
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
    operator: str = _DEFAULT_OPERATOR,
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
        operator=operator,
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
    operator: str = _DEFAULT_OPERATOR,
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
        operator=operator,
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


async def _run_job(job: Job, ctx: _RunContext, client: LlamaClient) -> None:
    """Generate one artefact, render it, write manifests, and mark the job SUCCEEDED or FAILED."""
    agent = ctx.agents[job.artefact_type.value]
    await _transition(ctx.store, job, JobStatus.RUNNING, ctx.clock)
    try:
        artefact = await agent.run(ctx.dossier_text, ctx.request.params, client, stream=ctx.stream)
    except AgentError as exc:
        job.error = str(exc)
        await _transition(ctx.store, job, JobStatus.FAILED, ctx.clock)
        return
    job_dir = ctx.out_root / job.id
    json_path = Path(_write_artefact(job_dir, agent.artefact_type, artefact))
    rendered = render(artefact, job_dir, formats=FORMATS.get(agent.artefact_type, ()))
    _emit_manifests([json_path, *rendered], job=job, agent=agent, ctx=ctx)
    job.artefact_path = str(json_path)
    await _transition(ctx.store, job, JobStatus.SUCCEEDED, ctx.clock)


def _emit_manifests(paths: list[Path], *, job: Job, agent: ArtefactAgent, ctx: _RunContext) -> None:
    """Write a provenance manifest beside every produced file."""
    meta = ctx.manager.model_meta(job.model_key)
    params = ctx.request.params.model_dump(mode="json")
    for path in paths:
        manifest = Manifest(
            source_sha256=ctx.dossier_sha,
            artefact_type=agent.artefact_type,
            artefact_format=path.suffix.lstrip("."),
            model_key=job.model_key,
            model_sha256=meta.get("sha256"),
            model_quant=str(meta.get("quant", "unknown")),
            prompt_version=agent.prompt_version,
            generation_params=params,
            created_at=job.created_at.isoformat(),
            rendered_at=ctx.clock().isoformat(),
            operator=ctx.operator,
            app_version=__version__,
            job_id=job.id,
            transform_id=job.transform_id,
        )
        write_manifest(path, manifest)


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


def _validate_sources(sources: list[SourceInput]) -> None:
    """Raise ConfigError naming the first file source whose path is not on disk."""
    for source in sources:
        if source.kind is SourceKind.file and not Path(source.path or "").is_file():
            raise ConfigError(f"source file not found: {source.path}", path=str(source.path))
