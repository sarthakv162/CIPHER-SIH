"""Phase 9c: the video's lower third carries the advisory's severity only when requested."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rupantar.agents.loader import load_agents
from rupantar.core.config import Env, load_config
from rupantar.core.schemas import ArtefactType, SourceInput, SourceKind, TransformRequest
from rupantar.core.store import Store
from rupantar.models.manager import ModelManager
from rupantar.models.registry import Registry
from rupantar.orchestrator.runner import run_batch


async def _run(
    configs_dir: Path,
    tmp_path: Path,
    fixtures: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_types: list[ArtefactType],
) -> Path:
    monkeypatch.setenv("RUPANTAR_STUB_COMPLETION", str(fixtures))
    db = tmp_path / "rupantar.db"
    config = load_config(configs_dir, env=Env(profile="test-stub", db=db))
    manager = ModelManager(Registry.from_config(config, verify=False), policy=config.policy)
    agents = load_agents(configs_dir / "agents")
    article = configs_dir.parent / "tests" / "fixtures" / "articles" / "ai_policy_brief.md"
    request = TransformRequest(
        sources=[SourceInput(kind=SourceKind.file, path=str(article))],
        output_types=output_types,
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
    video_job = next(j for j in jobs if j.artefact_type is ArtefactType.video_package)
    assert video_job.status.value == "SUCCEEDED"
    return tmp_path / video_job.id / "storyboard.json"


async def test_advisory_plus_video_carries_a_nonempty_severity(
    configs_dir: Path, artefacts_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    board_path = await _run(
        configs_dir,
        tmp_path,
        artefacts_dir,
        monkeypatch,
        [ArtefactType.advisory, ArtefactType.video_package],
    )
    board = json.loads(board_path.read_text())
    severities = {p["lower_third_severity"] for p in board["panels"]}
    assert severities == {"high"}  # the advisory fixture's severity


async def test_video_alone_has_no_severity(
    configs_dir: Path, artefacts_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    board_path = await _run(
        configs_dir, tmp_path, artefacts_dir, monkeypatch, [ArtefactType.video_package]
    )
    board = json.loads(board_path.read_text())
    assert all(p["lower_third_severity"] is None for p in board["panels"])
