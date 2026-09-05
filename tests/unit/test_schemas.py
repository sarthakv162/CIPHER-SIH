"""Request/job contract behaviour: validators, dedup, enums, round-trip."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from rupantar.core.schemas import (
    ArtefactType,
    GenerationParams,
    Job,
    JobStatus,
    SourceInput,
    SourceKind,
    TransformRequest,
)


def test_source_input_requires_exactly_one_payload() -> None:
    SourceInput(kind=SourceKind.text, text="hello")
    SourceInput(kind=SourceKind.file, path="/tmp/x.txt")

    with pytest.raises(ValidationError):
        SourceInput(kind=SourceKind.text)
    with pytest.raises(ValidationError):
        SourceInput(kind=SourceKind.text, text="a", path="/tmp/x")
    with pytest.raises(ValidationError):
        SourceInput(kind=SourceKind.file, text="a")


def test_transform_request_dedups_output_types_preserving_order() -> None:
    request = TransformRequest(
        sources=[SourceInput(kind=SourceKind.text, text="body")],
        output_types=[
            ArtefactType.advisory,
            ArtefactType.executive_summary,
            ArtefactType.advisory,
            ArtefactType.linkedin_post,
        ],
    )
    assert request.output_types == [
        ArtefactType.advisory,
        ArtefactType.executive_summary,
        ArtefactType.linkedin_post,
    ]


def test_transform_request_rejects_empty_lists() -> None:
    with pytest.raises(ValidationError):
        TransformRequest(sources=[], output_types=[ArtefactType.advisory])
    with pytest.raises(ValidationError):
        TransformRequest(sources=[SourceInput(kind=SourceKind.text, text="x")], output_types=[])


def test_generation_params_defaults() -> None:
    params = GenerationParams()
    assert params.language == "en"
    assert params.audience.value == "general_public"
    assert params.style.value == "plain"


def test_job_status_values() -> None:
    assert {s.value for s in JobStatus} == {
        "PENDING",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    }


def test_job_round_trips_through_json() -> None:
    now = datetime(2024, 9, 17, 8, 30, tzinfo=UTC)
    job = Job(
        id="job-1",
        transform_id="tr-1",
        artefact_type=ArtefactType.x_thread,
        model_key="brain",
        status=JobStatus.PENDING,
        depends_on=["job-0"],
        error=None,
        artefact_path=None,
        created_at=now,
        updated_at=now,
    )
    restored = Job.model_validate_json(job.model_dump_json())
    assert restored == job
