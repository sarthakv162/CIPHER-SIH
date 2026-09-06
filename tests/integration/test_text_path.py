"""Full text path with the stub runtime and zero model files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rupantar.agents.loader import load_agents
from rupantar.core.artefacts import ExecutiveSummary
from rupantar.core.config import Env, load_config
from rupantar.core.schemas import (
    ArtefactType,
    Job,
    JobStatus,
    SourceInput,
    SourceKind,
    TransformRequest,
)
from rupantar.core.store import Store
from rupantar.models.manager import ModelManager
from rupantar.models.registry import Registry
from rupantar.orchestrator.runner import run_single


async def _run(
    configs_dir: Path, tmp_path: Path, completion: str, monkeypatch: pytest.MonkeyPatch
) -> Job:
    monkeypatch.setenv("RUPANTAR_STUB_COMPLETION", completion)
    db = tmp_path / "rupantar.db"
    config = load_config(configs_dir, env=Env(profile="test-stub", db=db))
    manager = ModelManager(Registry.from_config(config, verify=False), policy=config.policy)
    agents = load_agents(configs_dir / "agents")
    article = configs_dir.parent / "tests" / "fixtures" / "articles" / "ai_policy_brief.md"
    request = TransformRequest(
        sources=[SourceInput(kind=SourceKind.file, path=str(article))],
        output_types=[ArtefactType.executive_summary],
    )
    store = Store(db)
    await store.connect()
    try:
        async with manager:
            return await run_single(
                request, manager=manager, agents=agents, store=store, out_root=tmp_path
            )
    finally:
        await store.close()


async def test_valid_completion_produces_a_succeeded_job(
    configs_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = (
        configs_dir.parent / "tests" / "fixtures" / "artefacts" / "executive_summary.json"
    ).read_text(encoding="utf-8")
    job = await _run(configs_dir, tmp_path, json.dumps(json.loads(fixture)), monkeypatch)
    assert job.status is JobStatus.SUCCEEDED
    assert job.artefact_path is not None
    path = Path(job.artefact_path)
    assert path.is_file()
    ExecutiveSummary.model_validate_json(path.read_text(encoding="utf-8"))


async def test_invalid_completion_fails_the_job_cleanly(
    configs_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = await _run(configs_dir, tmp_path, '{"title": "x"}', monkeypatch)
    assert job.status is JobStatus.FAILED
    assert job.error is not None
    assert "executive_summary" in job.error
    assert "Traceback" not in job.error
    assert job.artefact_path is None
