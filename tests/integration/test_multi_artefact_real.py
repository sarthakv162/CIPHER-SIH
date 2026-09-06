"""Real-brain multi-artefact batch. Skips unless llama-server and the brain GGUF are present."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest

from rupantar.agents.loader import load_agents
from rupantar.core.artefacts import ARTEFACT_MODELS
from rupantar.core.config import Env, load_config
from rupantar.core.schemas import ArtefactType, SourceInput, SourceKind, TransformRequest
from rupantar.core.store import Store
from rupantar.models.manager import ModelManager
from rupantar.models.registry import Registry
from rupantar.orchestrator.runner import run_batch

pytestmark = pytest.mark.slow

_REPO = Path(__file__).resolve().parents[2]
_BRAIN = _REPO / "models" / "brain" / "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"


@pytest.mark.skipif(
    shutil.which("llama-server") is None or not _BRAIN.is_file(),
    reason="needs llama-server on PATH and the brain GGUF on disk",
)
async def test_real_brain_produces_seven_valid_artefacts(tmp_path: Path) -> None:
    db = tmp_path / "rupantar.db"
    config = load_config(_REPO / "configs", env=Env(profile="apple-metal", db=db))
    manager = ModelManager(Registry.from_config(config, verify=False), policy=config.policy)
    agents = load_agents(_REPO / "configs" / "agents")
    article = _REPO / "tests" / "fixtures" / "articles" / "ai_policy_brief.md"
    request = TransformRequest(
        sources=[SourceInput(kind=SourceKind.file, path=str(article))],
        output_types=list(ArtefactType),
    )
    store = Store(db)
    await store.connect()
    started = time.monotonic()
    try:
        async with manager:
            jobs = await run_batch(
                request, manager=manager, agents=agents, store=store, out_root=tmp_path
            )
    finally:
        await store.close()
    wall = time.monotonic() - started

    load_starts = [e for e in manager.events if e.model_key == "brain" and e.kind == "LOAD_START"]
    print(f"\n7-artefact real batch: {wall:.1f}s wall, {len(load_starts)} brain LOAD_START")
    assert len(load_starts) == 1
    for job in jobs:
        assert job.status.value == "SUCCEEDED", (job.artefact_type.value, job.error)
        model = ARTEFACT_MODELS[job.artefact_type.value]
        model.model_validate_json(Path(job.artefact_path or "").read_text(encoding="utf-8"))
