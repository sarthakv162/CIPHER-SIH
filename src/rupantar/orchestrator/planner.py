"""Planner: turn one TransformRequest into a list of Jobs with dependency edges."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime

from rupantar.agents.base import ArtefactAgent
from rupantar.core.errors import ConfigError
from rupantar.core.schemas import ArtefactType, Job, JobStatus, TransformRequest

_EXEC = ArtefactType.executive_summary
_VIDEO = ArtefactType.video_package
_INFOGRAPHIC = ArtefactType.infographic_spec
_ADVISORY = ArtefactType.advisory


def plan(
    request: TransformRequest,
    agents: Mapping[str, ArtefactAgent],
    *,
    new_id: Callable[[], str],
    clock: Callable[[], datetime],
) -> list[Job]:
    """Build one PENDING Job per requested output type, recording known dependency edges."""
    transform_id = new_id()
    now = clock()
    jobs: list[Job] = []
    by_type: dict[ArtefactType, Job] = {}
    for output_type in request.output_types:
        agent = agents.get(output_type.value)
        if agent is None:
            raise ConfigError(
                f"no agent configured for {output_type.value!r}; add "
                f"configs/agents/{output_type.value}.yaml",
                key=output_type.value,
            )
        job = Job(
            id=new_id(),
            transform_id=transform_id,
            artefact_type=output_type,
            model_key=agent.model_key,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        jobs.append(job)
        by_type[output_type] = job

    video = by_type.get(_VIDEO)
    if video is not None:
        edges = [
            src.id
            for src in (by_type.get(_EXEC), by_type.get(_INFOGRAPHIC), by_type.get(_ADVISORY))
            if src is not None
        ]
        if edges:
            video.depends_on = [*video.depends_on, *edges]
    return jobs
