"""SSE stream: job transitions, model events, token deltas, verification, and termination."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rupantar.api.app import create_app
from rupantar.api.events import EventBus
from rupantar.core.config import AppConfig, Env, load_config
from rupantar.core.schemas import ArtefactType

_ALL_TYPES = [t.value for t in ArtefactType]


@pytest.fixture
def stub_config(
    configs_dir: Path, artefacts_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AppConfig:
    """Test-stub profile, a throwaway database, and no frontend build on disk."""
    monkeypatch.setenv("RUPANTAR_STUB_COMPLETION", str(artefacts_dir))
    monkeypatch.setenv("RUPANTAR_FRONTEND_DIST", str(tmp_path / "no-such-dist"))
    return load_config(configs_dir, env=Env(profile="test-stub", db=tmp_path / "rupantar.db"))


@pytest.fixture
def api(stub_config: AppConfig) -> Iterator[tuple[TestClient, FastAPI]]:
    """A TestClient with the app lifespan active."""
    app = create_app(stub_config)
    with TestClient(app) as client:
        yield client, app


def _article(configs_dir: Path) -> str:
    return str(configs_dir.parent / "tests" / "fixtures" / "articles" / "ai_policy_brief.md")


def _post(client: TestClient, configs_dir: Path, outputs: list[str]) -> str:
    body = {"sources": [{"kind": "file", "path": _article(configs_dir)}], "output_types": outputs}
    response = client.post("/transforms", json=body)
    assert response.status_code == 202
    return str(response.json()["transform_id"])


def _read_frames(client: TestClient, url: str) -> list[dict[str, Any]]:
    """Consume an SSE stream to completion, returning parsed `{event, data}` frames."""
    frames: list[dict[str, Any]] = []
    with client.stream("GET", url) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        name: str | None = None
        for line in response.iter_lines():
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: ") and name is not None:
                frames.append({"event": name, "data": json.loads(line[len("data: ") :])})
                name = None
    return frames


def _grouped(frames: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for frame in frames:
        out.setdefault(frame["event"], []).append(frame["data"])
    return out


def test_unknown_transform_id_is_a_404(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api
    response = client.get("/transforms/does-not-exist/events")
    assert response.status_code == 404
    assert "does-not-exist" in response.json()["detail"]


def test_stream_terminates_and_reports_the_final_transform_state(
    api: tuple[TestClient, FastAPI], configs_dir: Path
) -> None:
    client, _ = api
    transform_id = _post(client, configs_dir, ["executive_summary", "advisory"])

    frames = _read_frames(client, f"/transforms/{transform_id}/events")

    assert frames[0]["event"] == "snapshot"
    assert frames[0]["data"]["transform_id"] == transform_id
    assert "models" in frames[0]["data"]
    assert frames[-1]["event"] == "transform"
    assert frames[-1]["data"]["final"] is True
    assert client.get(f"/transforms/{transform_id}").json()["status"] == "SUCCEEDED"


def test_stream_carries_job_transitions_tokens_and_verification(
    api: tuple[TestClient, FastAPI], configs_dir: Path
) -> None:
    client, _ = api
    transform_id = _post(client, configs_dir, _ALL_TYPES)

    frames = _read_frames(client, f"/transforms/{transform_id}/events")
    by_event = _grouped(frames)

    jobs = by_event.get("job", [])
    assert jobs, "no job transitions were streamed"
    assert "RUNNING" in {j["status"] for j in jobs}
    assert "SUCCEEDED" in {j["status"] for j in jobs}
    assert all(j["transform_id"] == transform_id for j in jobs)
    assert all(j["artefact_type"] in _ALL_TYPES for j in jobs)

    tokens = by_event.get("token", [])
    assert tokens, "no generation token deltas were streamed"
    assert {t["job_id"] for t in tokens} <= {j["job_id"] for j in jobs}
    assert all(isinstance(t["delta"], str) for t in tokens)

    verifications = by_event.get("verification", [])
    assert verifications, "the verification report never arrived as its own event"
    assert verifications[0]["transform_id"] == transform_id
    assert {"ok", "summary", "warnings", "conflicts"} <= set(verifications[0])

    names = [f["event"] for f in frames]
    assert names[-1] == "transform"
    assert names.index("verification") < len(names) - 1, "verification must be its own event"


def test_a_late_subscriber_gets_the_final_state_and_the_stream_closes(
    api: tuple[TestClient, FastAPI], configs_dir: Path
) -> None:
    client, _ = api
    transform_id = _post(client, configs_dir, ["executive_summary"])
    for _ in range(400):
        if client.get(f"/transforms/{transform_id}").json()["status"] in {"SUCCEEDED", "FAILED"}:
            break
        time.sleep(0.05)

    frames = _read_frames(client, f"/transforms/{transform_id}/events")
    assert frames[0]["event"] == "snapshot"
    assert frames[-1]["event"] == "transform"
    assert frames[-1]["data"]["final"] is True
    assert frames[-1]["data"]["status"] == "SUCCEEDED"


async def test_manager_events_reach_the_bus_with_key_pid_and_rss(stub_config: AppConfig) -> None:
    """create_app wires ModelManager's sink to the bus; acquire() stays the only load path."""
    app = create_app(stub_config)
    bus: EventBus = app.state.bus
    manager = app.state.manager
    rows: list[dict[str, Any]] = []
    try:
        with bus.subscribe("any-transform") as subscriber:
            async with manager.acquire("brain"):
                pass
            await manager.evict("brain")
            while not subscriber.queue.empty():
                frame = subscriber.queue.get_nowait()
                assert frame.name == "model"
                assert frame.transform_id is None
                rows.append(frame.data)
    finally:
        await manager.aclose()

    assert {"LOAD_START", "LOAD_READY", "EVICT_START", "EVICT_DONE"} <= {r["kind"] for r in rows}
    assert all(r["model_key"] == "brain" for r in rows)
    assert all("pid" in r and "rss_mb" in r for r in rows)
    ready = next(r for r in rows if r["kind"] == "LOAD_READY")
    assert ready["pid"] is not None
    assert next(r for r in rows if r["kind"] == "EVICT_DONE")["rss_mb"] == 0.0
