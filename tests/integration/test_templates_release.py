"""GET /templates and the operator release endpoint, end to end on the stub runtime."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rupantar.api.app import create_app
from rupantar.api.routes.templates import read_templates
from rupantar.core.config import Env, load_config


@pytest.fixture
def api(
    configs_dir: Path, artefacts_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, FastAPI]]:
    """A TestClient on the stub profile with a throwaway database and no frontend build."""
    monkeypatch.setenv("RUPANTAR_STUB_COMPLETION", str(artefacts_dir))
    monkeypatch.setenv("RUPANTAR_FRONTEND_DIST", str(tmp_path / "no-such-dist"))
    config = load_config(configs_dir, env=Env(profile="test-stub", db=tmp_path / "rupantar.db"))
    app = create_app(config)
    with TestClient(app) as client:
        yield client, app


def _article(configs_dir: Path) -> str:
    return str(configs_dir.parent / "tests" / "fixtures" / "articles" / "ai_policy_brief.md")


def _run_one(client: TestClient, configs_dir: Path) -> dict[str, Any]:
    """Run a one-artefact transform and wait on the SSE terminal event, which lands after
    `_emit_all_manifests` — polling status alone can observe SUCCEEDED before the manifests."""
    body = {
        "sources": [{"kind": "file", "path": _article(configs_dir)}],
        "output_types": ["executive_summary"],
    }
    transform_id = client.post("/transforms", json=body).json()["transform_id"]
    with client.stream("GET", f"/transforms/{transform_id}/events") as stream:
        for line in stream.iter_lines():
            if line.startswith("data: ") and json.loads(line[len("data: ") :]).get("final"):
                break
    payload = dict(client.get(f"/transforms/{transform_id}").json())
    assert payload["status"] in {"SUCCEEDED", "FAILED"}
    return payload


def test_templates_lists_ntro_formal(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api
    response = client.get("/templates")
    assert response.status_code == 200
    entries = response.json()
    by_name = {entry["name"]: entry for entry in entries}
    assert "ntro-formal" in by_name
    entry = by_name["ntro-formal"]
    assert entry["label"] == "NTRO Formal"
    assert entry["description"]
    assert entry["accent"].startswith("#")


def test_templates_does_not_add_a_generation_parameter(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api
    schema = client.get("/openapi.json").json()["components"]["schemas"]["GenerationParams"]
    assert "template" not in schema["properties"]


def test_read_templates_is_empty_when_the_directory_is_missing(tmp_path: Path) -> None:
    assert read_templates(tmp_path / "nope") == []


def test_release_stamps_the_manifest_and_keeps_every_field(
    api: tuple[TestClient, FastAPI], configs_dir: Path
) -> None:
    client, _ = api
    terminal = _run_one(client, configs_dir)
    transform_id = terminal["transform_id"]
    job = terminal["jobs"][0]
    manifests = sorted(Path(job["artefact_path"]).parent.glob("*.manifest.json"))
    assert manifests, "the job wrote no manifest to release"
    before = {p: json.loads(p.read_text(encoding="utf-8")) for p in manifests}

    response = client.post(
        f"/transforms/{transform_id}/jobs/{job['id']}/release",
        json={
            "operator": "duty-officer",
            "acknowledged_claim_ids": ["C1", "C4"],
            "acknowledged_relations": ["endpoint-count"],
            "note": "Reconciled against the regional roll-up.",
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["released_by"] == "duty-officer"
    assert result["released_at"]
    assert len(result["manifests"]) == len(manifests)

    for path, original in before.items():
        after = json.loads(path.read_text(encoding="utf-8"))
        assert set(after) == set(original) | {"release"}
        for key, value in original.items():
            if key != "release":
                assert after[key] == value
        assert after["release"]["released_by"] == "duty-officer"
        assert after["release"]["acknowledged_claim_ids"] == ["C1", "C4"]
        assert after["release"]["acknowledged_relations"] == ["endpoint-count"]
        assert after["release"]["note"].startswith("Reconciled")


def test_release_creates_no_unmanifested_artefact_file(
    api: tuple[TestClient, FastAPI], configs_dir: Path
) -> None:
    client, _ = api
    terminal = _run_one(client, configs_dir)
    job = terminal["jobs"][0]
    job_dir = Path(job["artefact_path"]).parent
    before = sorted(p.name for p in job_dir.iterdir())

    client.post(
        f"/transforms/{terminal['transform_id']}/jobs/{job['id']}/release",
        json={"operator": "duty-officer"},
    )
    assert sorted(p.name for p in job_dir.iterdir()) == before
    for path in job_dir.iterdir():
        if path.is_file() and not path.name.endswith(".manifest.json"):
            assert path.with_name(path.name + ".manifest.json").is_file()


def test_release_404s_on_an_unknown_transform(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api
    response = client.post(
        "/transforms/nope/jobs/also-nope/release", json={"operator": "duty-officer"}
    )
    assert response.status_code == 404
    assert "nope" in response.json()["detail"]


def test_release_404s_on_a_job_outside_the_transform(
    api: tuple[TestClient, FastAPI], configs_dir: Path
) -> None:
    client, _ = api
    terminal = _run_one(client, configs_dir)
    response = client.post(
        f"/transforms/{terminal['transform_id']}/jobs/not-a-real-job/release",
        json={"operator": "duty-officer"},
    )
    assert response.status_code == 404
    assert "not-a-real-job" in response.json()["detail"]


def test_release_requires_an_operator(api: tuple[TestClient, FastAPI], configs_dir: Path) -> None:
    client, _ = api
    terminal = _run_one(client, configs_dir)
    job = terminal["jobs"][0]
    url = f"/transforms/{terminal['transform_id']}/jobs/{job['id']}/release"
    assert client.post(url, json={}).status_code == 422
    assert client.post(url, json={"operator": ""}).status_code == 422
