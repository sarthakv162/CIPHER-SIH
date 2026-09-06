"""planner.plan: one job per output type, model_key from the agent, dependency edges."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime
from pathlib import Path

import pytest

from rupantar.agents.loader import load_agents
from rupantar.core.errors import ConfigError
from rupantar.core.schemas import (
    ArtefactType,
    JobStatus,
    SourceInput,
    SourceKind,
    TransformRequest,
)
from rupantar.orchestrator.planner import plan

_REPO = Path(__file__).resolve().parents[2]
_AGENTS = load_agents(_REPO / "configs" / "agents")


def _ids() -> object:
    counter = itertools.count()
    return lambda: f"id-{next(counter)}"


def _clock() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)


def _request(*types: ArtefactType) -> TransformRequest:
    return TransformRequest(
        sources=[SourceInput(kind=SourceKind.text, text="hello")],
        output_types=list(types),
    )


def test_one_job_per_output_type_in_order() -> None:
    request = _request(
        ArtefactType.linkedin_post, ArtefactType.executive_summary, ArtefactType.advisory
    )
    jobs = plan(request, _AGENTS, new_id=_ids(), clock=_clock)
    assert [job.artefact_type for job in jobs] == request.output_types
    assert all(job.status is JobStatus.PENDING for job in jobs)
    assert all(job.model_key == "brain" for job in jobs)
    assert len({job.transform_id for job in jobs}) == 1
    assert all(job.depends_on == [] for job in jobs)


def test_video_package_depends_on_executive_summary_when_both_present() -> None:
    for order in (
        (ArtefactType.executive_summary, ArtefactType.video_package),
        (ArtefactType.video_package, ArtefactType.executive_summary),
    ):
        jobs = plan(_request(*order), _AGENTS, new_id=_ids(), clock=_clock)
        by_type = {job.artefact_type: job for job in jobs}
        video = by_type[ArtefactType.video_package]
        assert video.depends_on == [by_type[ArtefactType.executive_summary].id]


def test_video_package_alone_has_no_dependency() -> None:
    jobs = plan(_request(ArtefactType.video_package), _AGENTS, new_id=_ids(), clock=_clock)
    assert jobs[0].depends_on == []


def test_missing_agent_raises_config_error_naming_the_yaml() -> None:
    agents = {k: v for k, v in _AGENTS.items() if k != "advisory"}
    with pytest.raises(ConfigError) as excinfo:
        plan(_request(ArtefactType.advisory), agents, new_id=_ids(), clock=_clock)
    assert "configs/agents/advisory.yaml" in str(excinfo.value)
