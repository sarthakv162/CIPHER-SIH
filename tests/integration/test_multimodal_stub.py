"""Multimodal ingestion on the stub runtime: vlm -> evict -> asr -> evict -> brain."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from rupantar.agents.loader import load_agents
from rupantar.core.config import Env, load_config
from rupantar.core.schemas import ArtefactType, SourceInput, SourceKind, TransformRequest
from rupantar.core.store import Store
from rupantar.models.manager import ModelManager
from rupantar.models.registry import Registry
from rupantar.orchestrator.runner import run_batch

_REPO = Path(__file__).resolve().parents[2]
_MEDIA = _REPO / "tests" / "fixtures" / "media"
_ARTICLE = _REPO / "tests" / "fixtures" / "articles" / "ai_policy_brief.md"
_STUB_TRANSCRIPT = "The speaker outlines an offline first architecture for sensitive workloads."

_HEAVY = {"vlm", "brain"}
_EXPECTED = [
    ("LOAD_START", "vlm"),
    ("LOAD_READY", "vlm"),
    ("EVICT_START", "vlm"),
    ("EVICT_DONE", "vlm"),
    ("LOAD_START", "asr"),
    ("LOAD_READY", "asr"),
    ("EVICT_START", "asr"),
    ("EVICT_DONE", "asr"),
    ("LOAD_START", "brain"),
    ("LOAD_READY", "brain"),
]


async def _run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Store, str, ModelManager]:
    completions = tmp_path / "completions"
    completions.mkdir()
    shutil.copy(_REPO / "tests" / "fixtures" / "artefacts" / "executive_summary.json", completions)
    shutil.copy(_REPO / "tests" / "fixtures" / "ingest" / "ImageInsight.json", completions)
    monkeypatch.setenv("RUPANTAR_STUB_COMPLETION", str(completions))
    monkeypatch.setenv("RUPANTAR_STUB_TRANSCRIPT", _STUB_TRANSCRIPT)

    db = tmp_path / "rupantar.db"
    config = load_config(_REPO / "configs", env=Env(profile="test-stub", db=db))
    manager = ModelManager(Registry.from_config(config, verify=False), policy=config.policy)
    agents = load_agents(_REPO / "configs" / "agents")
    request = TransformRequest(
        sources=[
            SourceInput(kind=SourceKind.file, path=str(_MEDIA / "sample_image.png")),
            SourceInput(kind=SourceKind.file, path=str(_MEDIA / "sample_clip.mp4")),
            SourceInput(kind=SourceKind.file, path=str(_ARTICLE)),
        ],
        output_types=[ArtefactType.executive_summary],
    )
    store = Store(db)
    await store.connect()
    async with manager:
        jobs = await run_batch(
            request, manager=manager, agents=agents, store=store, out_root=tmp_path
        )
    assert all(job.status.value == "SUCCEEDED" for job in jobs), [
        (j.artefact_type.value, j.error) for j in jobs
    ]
    return store, jobs[0].transform_id, manager


def _heavy_events(manager: ModelManager) -> list[tuple[str, str]]:
    kinds = {"LOAD_START", "LOAD_READY", "EVICT_START", "EVICT_DONE", "PROCESS_DIED"}
    return [
        (e.kind, e.model_key)
        for e in manager.events
        if e.kind in kinds and e.model_key in {"vlm", "asr", "brain"}
    ]


async def test_modality_swap_order_and_never_two_heavy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, transform_id, manager = await _run(tmp_path, monkeypatch)
    try:
        observed = _heavy_events(manager)
        assert observed[:10] == _EXPECTED
        assert observed[10:] in ([], [("EVICT_START", "brain"), ("EVICT_DONE", "brain")])

        resident: set[str] = set()
        for kind, key in observed:
            if kind == "LOAD_READY":
                resident.add(key)
            elif kind in {"EVICT_START", "EVICT_DONE", "PROCESS_DIED"}:
                resident.discard(key)
            assert not _HEAVY.issubset(resident), f"two heavy models resident: {resident}"
    finally:
        await store.close()


async def test_dossier_merges_every_modality(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, transform_id, _manager = await _run(tmp_path, monkeypatch)
    try:
        dossier = await store.get_dossier(transform_id)
    finally:
        await store.close()
    assert dossier is not None
    assert dossier.text_blocks and dossier.image_insights and dossier.transcripts

    prompt_text = dossier.to_prompt_text()
    assert "modern data centre aisle" in prompt_text
    assert _STUB_TRANSCRIPT in prompt_text
