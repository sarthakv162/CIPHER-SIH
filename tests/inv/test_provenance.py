"""INV-5: every artefact file written to disk has a sibling .manifest.json.

Run a real batch transform through run_batch on the stub runtime (fixtures serve the
canned completions), then assert every non-manifest file in each job directory has a
sibling manifest that parses as Manifest with a non-empty source_sha256 and model_key.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rupantar.agents.loader import load_agents
from rupantar.audit.provenance import Manifest, is_manifest
from rupantar.core.config import Env, load_config
from rupantar.core.schemas import ArtefactType, SourceInput, SourceKind, TransformRequest
from rupantar.core.store import Store
from rupantar.models.manager import ModelManager
from rupantar.models.registry import Registry
from rupantar.orchestrator.runner import run_batch

_REPO = Path(__file__).resolve().parents[2]
_CONFIGS = _REPO / "configs"
_ARTEFACTS = _REPO / "tests" / "fixtures" / "artefacts"
_ARTICLE = _REPO / "tests" / "fixtures" / "articles" / "ai_policy_brief.md"


async def test_every_artefact_file_has_a_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each produced file (json + rendered) gets a valid sibling manifest."""
    monkeypatch.setenv("RUPANTAR_STUB_COMPLETION", str(_ARTEFACTS))
    outputs = tmp_path / "outputs"
    config = load_config(_CONFIGS, env=Env(profile="test-stub", db=tmp_path / "rupantar.db"))
    manager = ModelManager(Registry.from_config(config, verify=False), policy=config.policy)
    agents = load_agents(_CONFIGS / "agents")
    request = TransformRequest(
        sources=[SourceInput(kind=SourceKind.file, path=str(_ARTICLE))],
        output_types=[ArtefactType.advisory, ArtefactType.presentation, ArtefactType.x_thread],
    )
    store = Store(tmp_path / "rupantar.db")
    await store.connect()
    try:
        async with manager:
            jobs = await run_batch(
                request, manager=manager, agents=agents, store=store, out_root=outputs
            )
    finally:
        await store.close()

    assert all(job.status.value == "SUCCEEDED" for job in jobs)
    checked = 0
    for job in jobs:
        files = [p for p in (outputs / job.id).iterdir() if p.is_file() and not is_manifest(p)]
        assert files, f"job {job.artefact_type.value} produced no files"
        for path in files:
            manifest_file = path.with_name(path.name + ".manifest.json")
            assert manifest_file.is_file(), f"no manifest for {path.name}"
            manifest = Manifest.model_validate_json(manifest_file.read_text(encoding="utf-8"))
            assert manifest.source_sha256
            assert manifest.model_key
            assert manifest.artefact_format == path.suffix.lstrip(".")
            checked += 1
    assert checked >= 6
