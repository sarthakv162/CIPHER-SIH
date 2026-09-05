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
