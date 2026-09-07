"""Batch orchestration: one dossier, modality-grouped leases, one artefact file per job."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rupantar.agents.base import ArtefactAgent
from rupantar.audit.egress import scan_egress
from rupantar.audit.provenance import Manifest, app_version, write_manifest
from rupantar.core.artefacts import ArtefactBase, InfographicSpec
from rupantar.core.errors import AgentError, ConfigError
from rupantar.core.schemas import (
    ArtefactType,
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
from rupantar.orchestrator._video_prep import ensure_infographic_spec, file_source_paths
from rupantar.orchestrator.planner import plan
from rupantar.orchestrator.scheduler import schedule
from rupantar.render.base import FORMATS, render
from rupantar.render.context import RenderContext
from rupantar.verify.report import VerificationReport, run_verification

_THEME_NAME = "ntro-formal"


def resolve_operator(explicit: str | None = None) -> str:
    """The named operator, else $USER, else 'unknown' — manifests always record someone."""
    return explicit or os.environ.get("USER") or "unknown"


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
    dossier: SourceDossier
    source_paths: list[Path]
    request: TransformRequest
    store: Store
    out_root: Path
    manager: ModelManager
    operator: str
    clock: Callable[[], datetime]
    stream: bool
    strict_airgap: bool
    infographic_holder: dict[str, InfographicSpec] = field(default_factory=dict)
    verification_params: dict[str, Any] | None = None

    def render_context(self) -> RenderContext:
        """A fresh RenderContext for the video renderer from this run's material."""
        return RenderContext(
            theme_name=_THEME_NAME,
            dossier=self.dossier,
            source_paths=list(self.source_paths),
            infographic_spec=self.infographic_holder.get("spec"),
        )


@dataclass
class _JobOutcome:
    """One succeeded job: its agent, validated artefact, and every file it produced."""

    job: Job
    agent: ArtefactAgent
    artefact: ArtefactBase
    paths: list[Path] = field(default_factory=list)


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
    strict_airgap: bool = False,
    operator: str | None = None,
    clock: Callable[[], datetime] = _utcnow,
    verification_params: dict[str, Any] | None = None,
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
        dossier=dossier,
        source_paths=file_source_paths(request.sources),
        request=request,
        store=store,
        out_root=out_root,
        manager=manager,
        operator=resolve_operator(operator),
        clock=clock,
        stream=stream,
        strict_airgap=strict_airgap,
        verification_params=verification_params,
    )

    succeeded: list[_JobOutcome] = []
    report: VerificationReport | None = None
    for group in _consecutive_runs(schedule(jobs)):
        async with manager.acquire(group[0].model_key) as lease:
            client = LlamaClient(lease.endpoint, read_timeout=_client_read_timeout(ctx))
            try:
                group_results = await _run_group(group, ctx, client)
                if group[0].model_key == "brain" and group_results:
                    report = await _verify_group(transform_id, group_results, ctx, client)
                succeeded.extend(group_results)
            finally:
                await client.aclose()
    _emit_all_manifests(succeeded, report, ctx)
    return await store.list_jobs_for_transform(transform_id)


async def run_batch(
    request: TransformRequest,
    *,
    manager: ModelManager,
    agents: Mapping[str, ArtefactAgent],
    store: Store,
    out_root: Path,
    stream: bool = False,
    strict_airgap: bool = False,
    operator: str | None = None,
    clock: Callable[[], datetime] = _utcnow,
    new_id: Callable[[], str] = _uuid,
    verification_params: dict[str, Any] | None = None,
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
        strict_airgap=strict_airgap,
        operator=operator,
        clock=clock,
        verification_params=verification_params,
    )


async def run_single(
    request: TransformRequest,
    *,
    manager: ModelManager,
    agents: Mapping[str, ArtefactAgent],
    store: Store,
    out_root: Path,
    stream: bool = False,
    strict_airgap: bool = False,
    operator: str | None = None,
    clock: Callable[[], datetime] = _utcnow,
    new_id: Callable[[], str] = _uuid,
    verification_params: dict[str, Any] | None = None,
) -> Job:
    """Run only the first requested output type; a thin wrapper over `run_batch`."""
    jobs = await run_batch(
        request,
        manager=manager,
        agents=agents,
        store=store,
        out_root=out_root,
        stream=stream,
        strict_airgap=strict_airgap,
        operator=operator,
        clock=clock,
        new_id=new_id,
        verification_params=verification_params,
    )
    return jobs[0]


def _client_read_timeout(ctx: _RunContext) -> float:
    """HTTP read timeout for this group's client: past `LlamaClient`'s default only if the
    verification budget could otherwise exceed it -- a slow verification call must hit
    `run_verification`'s own asyncio timeout, not an opaque lower-level httpx ReadTimeout."""
    budget = float((ctx.verification_params or {}).get("timeout_seconds", 0))
    return max(300.0, budget + 30.0)


def _consecutive_runs(jobs: list[Job]) -> list[list[Job]]:
    """Split an ordered job list into maximal runs sharing one model_key."""
    runs: list[list[Job]] = []
    for job in jobs:
        if runs and runs[-1][0].model_key == job.model_key:
            runs[-1].append(job)
        else:
            runs.append([job])
    return runs


async def _run_group(group: list[Job], ctx: _RunContext, client: LlamaClient) -> list[_JobOutcome]:
    """Run every job of one modality group; return only the ones that succeeded."""
    await ensure_infographic_spec(group, ctx, client)
    results: list[_JobOutcome] = []
    for job in group:
        outcome = await _run_job(job, ctx, client)
        if outcome is None:
            continue
        if job.artefact_type is ArtefactType.infographic_spec and isinstance(
            outcome.artefact, InfographicSpec
        ):
            ctx.infographic_holder["spec"] = outcome.artefact
        results.append(outcome)
    return results


async def _run_job(job: Job, ctx: _RunContext, client: LlamaClient) -> _JobOutcome | None:
    """Generate one artefact, render it, and mark the job SUCCEEDED; None signals a failure."""
    agent = ctx.agents[job.artefact_type.value]
    await _transition(ctx.store, job, JobStatus.RUNNING, ctx.clock)
    if await _egress_aborts(ctx, job):
        return None
    try:
        artefact = await agent.run(ctx.dossier_text, ctx.request.params, client, stream=ctx.stream)
    except AgentError as exc:
        job.error = str(exc)
        await _transition(ctx.store, job, JobStatus.FAILED, ctx.clock)
        return None
    if await _egress_aborts(ctx, job):
        return None
    job_dir = ctx.out_root / job.id
    json_path = Path(_write_artefact(job_dir, agent.artefact_type, artefact))
    render_ctx = ctx.render_context() if job.artefact_type is ArtefactType.video_package else None
    rendered = render(
        artefact, job_dir, formats=FORMATS.get(agent.artefact_type, ()), context=render_ctx
    )
    job.artefact_path = str(json_path)
    await _transition(ctx.store, job, JobStatus.SUCCEEDED, ctx.clock)
    return _JobOutcome(job=job, agent=agent, artefact=artefact, paths=[json_path, *rendered])


async def _verify_group(
    transform_id: str, outcomes: list[_JobOutcome], ctx: _RunContext, client: LlamaClient
) -> VerificationReport:
    """Run the two verification brain calls over one brain group's succeeded artefacts."""
    artefacts = [(outcome.agent.artefact_type, outcome.artefact) for outcome in outcomes]
    report = await run_verification(
        transform_id,
        artefacts,
        ctx.dossier_text,
        client,
        params=ctx.verification_params,
        clock=ctx.clock,
    )
    await ctx.store.save_verification_report(transform_id, report)
    return report


def _emit_all_manifests(
    outcomes: list[_JobOutcome], report: VerificationReport | None, ctx: _RunContext
) -> None:
    """Write a provenance manifest for every succeeded job's files, once verification is known."""
    for outcome in outcomes:
        verification = report.for_manifest(outcome.agent.artefact_type) if report else None
        _emit_manifests(
            outcome.paths,
            job=outcome.job,
            agent=outcome.agent,
            ctx=ctx,
            verification=verification,
        )


async def _egress_aborts(ctx: _RunContext, job: Job) -> bool:
    """Scan for non-loopback connections; fail the job when --strict-airgap and one is found."""
    report = scan_egress()
    if report.clean:
        return False
    if not ctx.strict_airgap:
        return False
    remotes = sorted({v.raddr for v in report.violations})
    job.error = (
        f"EGRESS_VIOLATION: non-loopback connections {remotes}; job aborted (--strict-airgap)"
    )
    await _transition(ctx.store, job, JobStatus.FAILED, ctx.clock)
    return True


def _emit_manifests(
    paths: list[Path],
    *,
    job: Job,
    agent: ArtefactAgent,
    ctx: _RunContext,
    verification: dict[str, Any] | None = None,
) -> None:
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
            app_version=app_version(),
            job_id=job.id,
            transform_id=job.transform_id,
            verification=verification,
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
