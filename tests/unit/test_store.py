"""Async SQLite CRUD for transforms, jobs, and dossiers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from rupantar.core.errors import StoreError
from rupantar.core.schemas import (
    ArtefactType,
    Job,
    JobStatus,
    SourceDossier,
    SourceInput,
    SourceKind,
    TextBlock,
    TransformRequest,
)
from rupantar.core.store import Store
from rupantar.verify.report import VerificationReport, VerificationSummary


def _job(job_id: str, transform_id: str, artefact: ArtefactType) -> Job:
    now = datetime(2024, 9, 17, tzinfo=UTC)
    return Job(
        id=job_id,
        transform_id=transform_id,
        artefact_type=artefact,
        model_key="brain",
        status=JobStatus.PENDING,
        depends_on=[],
        error=None,
        artefact_path=None,
        created_at=now,
        updated_at=now,
    )


async def test_transform_round_trip(db_path: Path) -> None:
    request = TransformRequest(
        sources=[SourceInput(kind=SourceKind.text, text="body")],
        output_types=[ArtefactType.advisory],
    )
    async with Store(db_path) as store:
        await store.create_transform("tr-1", request)
        assert await store.get_transform_request("tr-1") == request
        assert await store.get_transform_request("missing") is None


async def test_job_crud_and_listing(db_path: Path) -> None:
    async with Store(db_path) as store:
        await store.create_job(_job("j-1", "tr-1", ArtefactType.advisory))
        await store.create_job(_job("j-2", "tr-1", ArtefactType.x_thread))
        await store.create_job(_job("j-3", "tr-2", ArtefactType.linkedin_post))

        fetched = await store.get_job("j-1")
        assert fetched is not None
        fetched.status = JobStatus.SUCCEEDED
        fetched.artefact_path = "data/outputs/j-1/advisory.md"
        await store.update_job(fetched)

        again = await store.get_job("j-1")
        assert again is not None
        assert again.status is JobStatus.SUCCEEDED
        assert again.artefact_path == "data/outputs/j-1/advisory.md"

        jobs = await store.list_jobs_for_transform("tr-1")
        assert [j.id for j in jobs] == ["j-1", "j-2"]


async def test_update_unknown_job_raises(db_path: Path) -> None:
    async with Store(db_path) as store:
        with pytest.raises(StoreError):
            await store.update_job(_job("ghost", "tr-9", ArtefactType.presentation))


async def test_dossier_round_trip(db_path: Path) -> None:
    dossier = SourceDossier(
        id="dos-1",
        created_at=datetime(2024, 9, 17, tzinfo=UTC),
        sha256="0" * 64,
        text_blocks=[TextBlock(source_name="a.txt", text="hello world")],
        metadata={"origin": "test"},
    )
    async with Store(db_path) as store:
        await store.save_dossier(dossier)
        assert await store.get_dossier("dos-1") == dossier
        assert await store.get_dossier("nope") is None


async def test_events_append_and_filter(db_path: Path) -> None:
    async with Store(db_path) as store:
        await store.append_event(
            kind="LOAD_START", model_key="brain", pid=111, detail={"port": 8100}
        )
        await store.append_event(kind="LOAD_READY", model_key="brain", pid=111)
        await store.append_event(kind="LOAD_START", model_key="vlm", pid=222)

        brain_events = await store.list_events(model_key="brain")
        assert [e["kind"] for e in brain_events] == ["LOAD_START", "LOAD_READY"]
        assert brain_events[0]["detail"]["port"] == 8100
        assert brain_events[0]["pid"] == 111

        starts = await store.list_events(kind="LOAD_START")
        assert {e["model_key"] for e in starts} == {"brain", "vlm"}

        assert len(await store.list_events()) == 3


async def test_connection_before_connect_raises(db_path: Path) -> None:
    store = Store(db_path)
    with pytest.raises(StoreError):
        _ = store.connection


def _request(*artefacts: ArtefactType) -> TransformRequest:
    return TransformRequest(
        sources=[SourceInput(kind=SourceKind.text, text="body")],
        output_types=list(artefacts),
    )


async def _add_job(store: Store, job_id: str, transform_id: str, status: JobStatus) -> None:
    job = _job(job_id, transform_id, ArtefactType.advisory)
    job.status = status
    await store.create_job(job)


async def test_list_transforms_is_newest_first_and_honours_limit(db_path: Path) -> None:
    async with Store(db_path) as store:
        for index in range(4):
            await store.create_transform(f"tr-{index}", _request(ArtefactType.advisory))

        rows = await store.list_transforms()
        assert [r.transform_id for r in rows] == ["tr-3", "tr-2", "tr-1", "tr-0"]

        limited = await store.list_transforms(limit=2)
        assert [r.transform_id for r in limited] == ["tr-3", "tr-2"]


async def test_list_transforms_rejects_a_zero_limit(db_path: Path) -> None:
    async with Store(db_path) as store:
        with pytest.raises(StoreError):
            await store.list_transforms(limit=0)


async def test_list_transforms_reports_requested_types_and_job_count(db_path: Path) -> None:
    async with Store(db_path) as store:
        await store.create_transform("tr-1", _request(ArtefactType.advisory, ArtefactType.x_thread))
        await _add_job(store, "j-1", "tr-1", JobStatus.SUCCEEDED)
        await _add_job(store, "j-2", "tr-1", JobStatus.SUCCEEDED)

        (row,) = await store.list_transforms()
        assert row.output_types == ["advisory", "x_thread"]
        assert row.job_count == 2
        assert row.status == "SUCCEEDED"
        assert row.has_verification is False
        assert row.verification_ok is None
        assert row.conflicts == 0


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([JobStatus.SUCCEEDED, JobStatus.RUNNING, JobStatus.PENDING], "RUNNING"),
        ([JobStatus.SUCCEEDED, JobStatus.PENDING], "PENDING"),
        ([JobStatus.SUCCEEDED, JobStatus.FAILED], "FAILED"),
        ([JobStatus.SUCCEEDED, JobStatus.SUCCEEDED], "SUCCEEDED"),
        ([JobStatus.CANCELLED], "FAILED"),
        ([], "FAILED"),
    ],
)
async def test_list_transforms_folds_mixed_job_statuses(
    db_path: Path, statuses: list[JobStatus], expected: str
) -> None:
    async with Store(db_path) as store:
        await store.create_transform("tr-1", _request(ArtefactType.advisory))
        for index, status in enumerate(statuses):
            await _add_job(store, f"j-{index}", "tr-1", status)

        (row,) = await store.list_transforms()
        assert row.status == expected
        assert row.job_count == len(statuses)


async def test_list_transforms_carries_the_verification_conflict_count(db_path: Path) -> None:
    report = VerificationReport(
        transform_id="tr-1",
        generated_at="2026-09-09T00:00:00+00:00",
        summary=VerificationSummary(total=9, supported=7, unsupported=2, conflict=2, orphan=1),
    )
    async with Store(db_path) as store:
        await store.create_transform("tr-1", _request(ArtefactType.advisory))
        await store.create_transform("tr-2", _request(ArtefactType.advisory))
        await _add_job(store, "j-1", "tr-1", JobStatus.SUCCEEDED)
        await store.save_verification_report("tr-1", report)

        rows = {r.transform_id: r for r in await store.list_transforms()}
        assert rows["tr-1"].has_verification is True
        assert rows["tr-1"].verification_ok is True
        assert rows["tr-1"].conflicts == 2
        assert rows["tr-2"].has_verification is False
        assert rows["tr-2"].conflicts == 0


async def test_list_transforms_marks_a_failed_verification_run(db_path: Path) -> None:
    report = VerificationReport(
        transform_id="tr-1",
        generated_at="2026-09-09T00:00:00+00:00",
        ok=False,
        warnings=["verification timed out"],
    )
    async with Store(db_path) as store:
        await store.create_transform("tr-1", _request(ArtefactType.advisory))
        await store.save_verification_report("tr-1", report)

        (row,) = await store.list_transforms()
        assert row.has_verification is True
        assert row.verification_ok is False
        assert row.conflicts == 0
