"""Single-job orchestration: one source, one text agent, one validated artefact file."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
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


def _utcnow() -> datetime:
    """Timezone-aware present instant."""
    return datetime.now(UTC)


def _uuid() -> str:
    """A fresh hex identifier."""
    return uuid.uuid4().hex


async def run_single(
    request: TransformRequest,
    *,
    manager: ModelManager,
    agents: dict[str, ArtefactAgent],
    store: Store,
    out_root: Path,
    stream: bool = False,
    clock: Callable[[], datetime] = _utcnow,
    new_id: Callable[[], str] = _uuid,
) -> Job:
    """Run the first source through the first output type's agent and persist the result."""
    transform_id = new_id()
    await store.create_transform(transform_id, request)
    output_type = request.output_types[0]
    agent = agents.get(output_type.value)
    if agent is None:
        raise ConfigError(
            f"no agent configured for {output_type.value!r}; add "
            f"configs/agents/{output_type.value}.yaml",
            key=output_type.value,
        )

    dossier = _build_dossier(request.sources[0], clock=clock, new_id=new_id)
    await store.save_dossier(dossier)

    job = Job(
        id=new_id(),
        transform_id=transform_id,
        artefact_type=output_type,
        model_key=agent.model_key,
        status=JobStatus.PENDING,
        created_at=clock(),
        updated_at=clock(),
    )
    await store.create_job(job)
    await _transition(store, job, JobStatus.RUNNING, clock)

    try:
        artefact = await _generate(agent, dossier, request, manager, stream)
    except AgentError as exc:
        job.error = str(exc)
        await _transition(store, job, JobStatus.FAILED, clock)
        return job

    job.artefact_path = _write_artefact(out_root / job.id, agent.artefact_type, artefact)
    await _transition(store, job, JobStatus.SUCCEEDED, clock)
    return job


async def _generate(
    agent: ArtefactAgent,
    dossier: SourceDossier,
    request: TransformRequest,
    manager: ModelManager,
    stream: bool,
) -> ArtefactBase:
    """Acquire the one model the agent needs and run it, releasing the lease afterwards."""
    async with manager.acquire(agent.model_key) as lease:
        client = LlamaClient(lease.endpoint)
        try:
            return await agent.run(dossier.to_prompt_text(), request.params, client, stream=stream)
        finally:
            await client.aclose()


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
