"""Real-brain text path. Skips unless llama-server and the brain GGUF are present."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from rupantar.agents.loader import load_agents
from rupantar.core.artefacts import ExecutiveSummary
from rupantar.core.config import Env, load_config
from rupantar.core.schemas import (
    ArtefactType,
    JobStatus,
    SourceInput,
    SourceKind,
    TransformRequest,
)
from rupantar.core.store import Store
from rupantar.models.manager import ModelManager
from rupantar.models.registry import Registry
from rupantar.orchestrator.runner import run_single

pytestmark = pytest.mark.slow

_REPO = Path(__file__).resolve().parents[2]
_BRAIN = _REPO / "models" / "brain" / "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"


@pytest.mark.skipif(
    shutil.which("llama-server") is None or not _BRAIN.is_file(),
    reason="needs llama-server on PATH and the brain GGUF on disk",
)
async def test_real_brain_produces_valid_executive_summary(tmp_path: Path) -> None:
    db = tmp_path / "rupantar.db"
    config = load_config(_REPO / "configs", env=Env(profile="laptop-16gb", db=db))
    manager = ModelManager(Registry.from_config(config, verify=False), policy=config.policy)
    agents = load_agents(_REPO / "configs" / "agents")
    article = _REPO / "tests" / "fixtures" / "articles" / "ai_policy_brief.md"
    request = TransformRequest(
        sources=[SourceInput(kind=SourceKind.file, path=str(article))],
        output_types=[ArtefactType.executive_summary],
    )
    store = Store(db)
    await store.connect()
    try:
        async with manager:
            job = await run_single(
                request, manager=manager, agents=agents, store=store, out_root=tmp_path
            )
    finally:
        await store.close()

    assert job.status is JobStatus.SUCCEEDED, job.error
    assert job.artefact_path is not None
    ExecutiveSummary.model_validate_json(Path(job.artefact_path).read_text(encoding="utf-8"))
