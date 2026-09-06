"""Cross-artefact verification wired end-to-end: manifests, the status API, the CLI line,
and (slow, real brain) the canonical demo scenario -- a genuine numeric contradiction caught."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from rupantar.agents.loader import load_agents
from rupantar.api.app import create_app
from rupantar.audit.provenance import Manifest, is_manifest
from rupantar.cli.main import app as cli_app
from rupantar.core.config import Env, load_config
from rupantar.core.schemas import ArtefactType, SourceInput, SourceKind, TransformRequest
from rupantar.core.store import Store
from rupantar.models.manager import ModelManager
from rupantar.models.registry import Registry
from rupantar.orchestrator.runner import run_batch

_REPO = Path(__file__).resolve().parents[2]
_ARTICLE = _REPO / "tests" / "fixtures" / "articles" / "ai_policy_brief.md"
_INCIDENT = _REPO / "tests" / "fixtures" / "articles" / "incident_endpoint_count.md"
_BRAIN = _REPO / "models" / "brain" / "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"

_CLAIM_EXTRACTION = {
    "claims": [
        {
            "id": "C1",
            "claim": "4,200 endpoints were compromised",
            "artefact_type": "executive_summary",
            "cited_sources": ["E1"],
        },
        {
            "id": "C2",
            "claim": "5,000 endpoints were compromised",
            "artefact_type": "advisory",
            "cited_sources": ["E1"],
        },
    ]
}
_GROUNDING_REPORT = {
    "groundings": [
        {"claim_id": "C1", "status": "SUPPORTED", "evidence_ids": ["E1"]},
        {"claim_id": "C2", "status": "SUPPORTED", "evidence_ids": ["E1"]},
    ],
    "relations": [
        {
            "kind": "CONFLICT",
            "claim_ids": ["C1", "C2"],
            "subject": "endpoints compromised",
            "detail": "4,200 vs 5,000",
        }
    ],
}


def _fixtures_dir(tmp_path: Path, artefacts_dir: Path) -> Path:
    """Two artefact examples plus canned claim-extraction and grounding responses."""
    target = tmp_path / "fixtures"
    target.mkdir()
    for name in ("executive_summary.json", "advisory.json"):
        shutil.copy(artefacts_dir / name, target / name)
    (target / "claim_extraction.json").write_text(json.dumps(_CLAIM_EXTRACTION), encoding="utf-8")
    (target / "grounding_report.json").write_text(json.dumps(_GROUNDING_REPORT), encoding="utf-8")
    return target


async def test_manifests_carry_a_verification_block(
    configs_dir: Path, artefacts_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixtures = _fixtures_dir(tmp_path, artefacts_dir)
    monkeypatch.setenv("RUPANTAR_STUB_COMPLETION", str(fixtures))
    out_root = tmp_path / "out"
    config = load_config(configs_dir, env=Env(profile="test-stub", db=tmp_path / "rupantar.db"))
    manager = ModelManager(Registry.from_config(config, verify=False), policy=config.policy)
    agents = load_agents(configs_dir / "agents")
    request = TransformRequest(
        sources=[SourceInput(kind=SourceKind.file, path=str(_ARTICLE))],
        output_types=[ArtefactType.executive_summary, ArtefactType.advisory],
    )
    store = Store(tmp_path / "rupantar.db")
    await store.connect()
    try:
        async with manager:
            jobs = await run_batch(
                request, manager=manager, agents=agents, store=store, out_root=out_root
            )
    finally:
        await store.close()

    assert all(job.status.value == "SUCCEEDED" for job in jobs)
    checked = 0
    for job in jobs:
        for path in (out_root / job.id).iterdir():
            if path.is_file() and not is_manifest(path):
                manifest_file = path.with_name(path.name + ".manifest.json")
                manifest = Manifest.model_validate_json(manifest_file.read_text(encoding="utf-8"))
                assert manifest.verification is not None
                assert manifest.verification["ok"] is True
                assert manifest.verification["summary"]["conflict"] == 1
                checked += 1
    assert checked >= 2


@pytest.fixture
def api(
    configs_dir: Path, artefacts_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, Path]]:
    """A TestClient wired to the stub runtime and the two-artefact verification fixtures."""
    fixtures = _fixtures_dir(tmp_path, artefacts_dir)
    monkeypatch.setenv("RUPANTAR_STUB_COMPLETION", str(fixtures))
    config = load_config(configs_dir, env=Env(profile="test-stub", db=tmp_path / "rupantar.db"))
    app = create_app(config)
    with TestClient(app) as client:
        yield client, config.db_path.parent / "outputs"


def test_transform_status_carries_the_verification_summary(
    api: tuple[TestClient, Path],
) -> None:
    client, _out_root = api
    body = {
        "sources": [{"kind": "file", "path": str(_ARTICLE)}],
        "output_types": ["executive_summary", "advisory"],
    }
    accepted = client.post("/transforms", json=body)
    assert accepted.status_code == 202
    transform_id = accepted.json()["transform_id"]

    payload = _poll(client, transform_id)
    assert payload["status"] == "SUCCEEDED"
    verification = payload["verification"]
    assert verification is not None
    assert verification["ok"] is True
    assert verification["conflict"] == 1
    assert "CONFLICT" in verification["line"]


def _poll(client: TestClient, transform_id: str, tries: int = 400) -> dict[str, object]:
    """Wait for a terminal status; then, since verification saves after the last job does, wait
    a little longer for the `verification` block itself to land before handing back the payload."""
    import time

    payload: dict[str, object] = {}
    for _ in range(tries):
        payload = client.get(f"/transforms/{transform_id}").json()
        if payload["status"] in {"SUCCEEDED", "FAILED"} and payload.get("verification"):
            return payload
        time.sleep(0.02)
    if payload.get("status") not in {"SUCCEEDED", "FAILED"}:
        raise AssertionError("transform did not reach a terminal status")
    return payload


def test_cli_prints_the_verification_line(
    configs_dir: Path, artefacts_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixtures = _fixtures_dir(tmp_path, artefacts_dir)
    monkeypatch.setenv("RUPANTAR_STUB_COMPLETION", str(fixtures))
    monkeypatch.setenv("RUPANTAR_PROFILE", "test-stub")
    monkeypatch.setenv("RUPANTAR_DB", str(tmp_path / "rupantar.db"))
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        [
            "transform",
            "--text",
            str(_ARTICLE),
            "--output",
            "executive_summary,advisory",
            "--out-dir",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "verification:" in result.output
    assert "CONFLICT" in result.output


_BRAIN_MISSING = shutil.which("llama-server") is None or not _BRAIN.is_file()


@pytest.mark.slow
@pytest.mark.skipif(_BRAIN_MISSING, reason="needs llama-server on PATH and the brain GGUF on disk")
async def test_real_brain_catches_a_genuine_endpoint_count_conflict(tmp_path: Path) -> None:
    """The canonical demo scenario: two artefacts anchor on two different endpoint counts."""
    config = load_config(_REPO / "configs", env=Env(profile="apple-metal", db=tmp_path / "r.db"))
    manager = ModelManager(Registry.from_config(config, verify=False), policy=config.policy)
    agents = load_agents(_REPO / "configs" / "agents")
    request = TransformRequest(
        sources=[SourceInput(kind=SourceKind.file, path=str(_INCIDENT))],
        output_types=[ArtefactType.executive_summary, ArtefactType.advisory],
    )
    store = Store(tmp_path / "r.db")
    await store.connect()
    try:
        async with manager:
            jobs = await run_batch(
                request,
                manager=manager,
                agents=agents,
                store=store,
                out_root=tmp_path,
                verification_params=config.policy.get("verification", {}),
            )
        assert all(job.status.value == "SUCCEEDED" for job in jobs), [
            (j.artefact_type.value, j.error) for j in jobs
        ]
        report = await store.get_verification_report(jobs[0].transform_id)
    finally:
        await store.close()

    assert report is not None
    print(f"\nverification: {report.summarise() if report.ok else report.warnings}")
    assert report.ok, report.warnings
    conflicts = [r for r in report.relations if r.kind == "CONFLICT"]
    assert conflicts, (
        "expected the real brain to flag a CONFLICT between the two stated endpoint counts; "
        f"got relations={report.relations}"
    )
