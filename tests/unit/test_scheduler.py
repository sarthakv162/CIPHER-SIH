"""scheduler.schedule: modality-priority grouping, stable within a group, depends_on wins."""

from __future__ import annotations

from datetime import UTC, datetime

from rupantar.core.schemas import ArtefactType, Job, JobStatus
from rupantar.orchestrator.scheduler import schedule

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _job(job_id: str, model_key: str, depends_on: list[str] | None = None) -> Job:
    return Job(
        id=job_id,
        transform_id="t",
        artefact_type=ArtefactType.executive_summary,
        model_key=model_key,
        status=JobStatus.PENDING,
        depends_on=depends_on or [],
        created_at=_NOW,
        updated_at=_NOW,
    )


def test_vlm_jobs_come_before_brain_jobs() -> None:
    jobs = [
        _job("b1", "brain"),
        _job("v1", "vlm"),
        _job("b2", "brain"),
        _job("v2", "vlm"),
    ]
    ordered = [job.id for job in schedule(jobs)]
    assert ordered == ["v1", "v2", "b1", "b2"]


def test_full_pipeline_priority_order() -> None:
    jobs = [_job("x", "other"), _job("a", "asr"), _job("b", "brain"), _job("v", "vlm")]
    assert [job.model_key for job in schedule(jobs)] == ["vlm", "asr", "brain", "other"]


def test_same_model_dependency_is_respected_against_input_order() -> None:
    jobs = [_job("late", "brain", depends_on=["early"]), _job("early", "brain")]
    assert [job.id for job in schedule(jobs)] == ["early", "late"]


def test_all_brain_request_is_identity() -> None:
    jobs = [_job(name, "brain") for name in ("one", "two", "three", "four")]
    assert [job.id for job in schedule(jobs)] == ["one", "two", "three", "four"]


def test_unknown_model_keys_sort_last_alphabetically() -> None:
    jobs = [_job("z", "zeta"), _job("b", "brain"), _job("a", "alpha")]
    assert [job.id for job in schedule(jobs)] == ["b", "a", "z"]
