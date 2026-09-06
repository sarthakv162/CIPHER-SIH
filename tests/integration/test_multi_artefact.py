"""Multi-artefact batch on the stub runtime: one brain load, seven validated artefacts."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from rupantar.agents.loader import load_agents
from rupantar.core.artefacts import ARTEFACT_MODELS
from rupantar.core.config import Env, load_config
from rupantar.core.schemas import ArtefactType, Job, SourceInput, SourceKind, TransformRequest
from rupantar.core.store import Store
from rupantar.models.manager import ModelManager
from rupantar.models.registry import Registry
from rupantar.orchestrator.runner import run_batch

_ALL_TYPES = list(ArtefactType)


async def _run_batch(
    configs_dir: Path, tmp_path: Path, fixtures: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[list[Job], ModelManager]:
    monkeypatch.setenv("RUPANTAR_STUB_COMPLETION", str(fixtures))
    db = tmp_path / "rupantar.db"
    config = load_config(configs_dir, env=Env(profile="test-stub", db=db))
    manager = ModelManager(Registry.from_config(config, verify=False), policy=config.policy)
    agents = load_agents(configs_dir / "agents")
    article = configs_dir.parent / "tests" / "fixtures" / "articles" / "ai_policy_brief.md"
    request = TransformRequest(
        sources=[SourceInput(kind=SourceKind.file, path=str(article))],
        output_types=_ALL_TYPES,
    )
    store = Store(db)
    await store.connect()
    try:
        async with manager:
            jobs = await run_batch(
                request, manager=manager, agents=agents, store=store, out_root=tmp_path
            )
    finally:
        await store.close()
    return jobs, manager


def _brain_event_kinds(manager: ModelManager) -> list[str]:
    return [event.kind for event in manager.events if event.model_key == "brain"]


async def test_seven_artefacts_one_brain_load(
    configs_dir: Path, artefacts_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs, manager = await _run_batch(configs_dir, tmp_path, artefacts_dir, monkeypatch)

    kinds = _brain_event_kinds(manager)
    assert kinds.count("LOAD_START") == 1
    assert kinds.count("LOAD_READY") == 1
    assert "EVICT_START" not in kinds
    assert "PROCESS_DIED" not in kinds

    assert [job.artefact_type for job in jobs] == _ALL_TYPES
    assert all(job.status.value == "SUCCEEDED" for job in jobs), [
        (j.artefact_type.value, j.error) for j in jobs
    ]
    for job in jobs:
        assert job.artefact_path is not None
        model = ARTEFACT_MODELS[job.artefact_type.value]
        model.model_validate_json(Path(job.artefact_path).read_text(encoding="utf-8"))


async def test_one_broken_fixture_fails_only_its_job(
    configs_dir: Path, artefacts_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = tmp_path / "fixtures"
    shutil.copytree(artefacts_dir, broken)
    (broken / "advisory.json").write_text('{"title": "x"}', encoding="utf-8")

    jobs, manager = await _run_batch(configs_dir, tmp_path, broken, monkeypatch)

    by_type = {job.artefact_type: job for job in jobs}
    advisory = by_type.pop(ArtefactType.advisory)
    assert advisory.status.value == "FAILED"
    assert advisory.error is not None and "advisory" in advisory.error
    assert "Traceback" not in advisory.error
    assert all(job.status.value == "SUCCEEDED" for job in by_type.values())
    assert _brain_event_kinds(manager).count("LOAD_START") == 1
