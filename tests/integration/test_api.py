"""API integration on the stub runtime: full batch, status, artefacts, models, health."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rupantar.api.app import create_app
from rupantar.core.artefacts import ARTEFACT_MODELS
from rupantar.core.config import Env, load_config
from rupantar.core.schemas import ArtefactType

_ALL_TYPES = [t.value for t in ArtefactType]


@pytest.fixture
def api(
    configs_dir: Path, artefacts_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, FastAPI]]:
    """A TestClient (lifespan active) wired to the test-stub profile and a tmp database."""
    monkeypatch.setenv("RUPANTAR_STUB_COMPLETION", str(artefacts_dir))
    config = load_config(configs_dir, env=Env(profile="test-stub", db=tmp_path / "rupantar.db"))
    app = create_app(config)
    with TestClient(app) as client:
        yield client, app


def _article(configs_dir: Path) -> str:
    return str(configs_dir.parent / "tests" / "fixtures" / "articles" / "ai_policy_brief.md")


def _poll(client: TestClient, transform_id: str, tries: int = 200) -> dict[str, object]:
    for _ in range(tries):
        payload = client.get(f"/transforms/{transform_id}").json()
        if payload["status"] in {"SUCCEEDED", "FAILED"}:
            return payload
        time.sleep(0.05)
    raise AssertionError("transform did not reach a terminal status")


def test_full_batch_lifecycle(api: tuple[TestClient, FastAPI], configs_dir: Path) -> None:
    client, app = api
    body = {
        "sources": [{"kind": "file", "path": _article(configs_dir)}],
        "output_types": _ALL_TYPES,
    }

    accepted = client.post("/transforms", json=body)
    assert accepted.status_code == 202
    payload = accepted.json()
    assert payload["status"] == "accepted"
    transform_id = payload["transform_id"]
    assert len(payload["jobs"]) == 7

    terminal = _poll(client, transform_id)
    assert terminal["status"] == "SUCCEEDED"
    assert len(terminal["jobs"]) == 7

    artefacts = client.get(f"/transforms/{transform_id}/artefacts").json()
    assert len(artefacts) == 7
    for entry in artefacts:
        assert entry["status"] == "SUCCEEDED"
        ARTEFACT_MODELS[entry["artefact_type"]].model_validate(entry["artefact"])

    first = artefacts[0]
    job = client.get(f"/jobs/{first['job_id']}")
    assert job.status_code == 200
    assert job.json()["artefact_type"] == first["artefact_type"]

    brain_loads = [
        e for e in app.state.manager.events if e.model_key == "brain" and e.kind == "LOAD_START"
    ]
    assert len(brain_loads) == 1


def test_unknown_ids_return_404(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api
    assert client.get("/transforms/does-not-exist").status_code == 404
    assert client.get("/transforms/does-not-exist/artefacts").status_code == 404
    assert client.get("/jobs/does-not-exist").status_code == 404


def test_model_routes(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api
    listing = client.get("/models")
    assert listing.status_code == 200
    assert len(listing.json()) == 4

    status = client.get("/models/status")
    assert status.status_code == 200
    assert len(status.json()) == 4

    assert client.post("/models/brain/unload").status_code == 200
    assert client.post("/models/ghost/unload").status_code == 404


def test_health(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api
    payload = client.get("/health").json()
    assert payload["status"] == "ok"
    assert payload["profile"] == "test-stub"
    assert payload["python"].startswith("3.11")
