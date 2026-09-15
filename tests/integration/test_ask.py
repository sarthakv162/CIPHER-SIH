"""POST /transforms/{id}/ask and POST /qa/sessions[/{id}/ask]: streamed, grounded Q&A.

The stub runtime (no `response_format` on the ask request) echoes the last user message,
so the question itself is the deterministic expected answer text here.
"""

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
from rupantar.core.config import AppConfig, Env, load_config
from rupantar.core.schemas import GenerationParams, SourceInput, SourceKind, TransformRequest
from rupantar.orchestrator.runner import prepare


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


def _read_sse(response: Any) -> list[dict[str, Any]]:
    """Parse a completed SSE response body into `{event, data}` frames."""
    frames: list[dict[str, Any]] = []
    name: str | None = None
    for line in response.iter_lines():
        if line.startswith("event: "):
            name = line[len("event: ") :]
        elif line.startswith("data: ") and name is not None:
            frames.append({"event": name, "data": json.loads(line[len("data: ") :])})
            name = None
    return frames


def _answer_text(frames: list[dict[str, Any]]) -> str:
    return "".join(f["data"]["text"] for f in frames if f["event"] == "delta")


def test_unknown_transform_ask_is_a_404(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api
    response = client.post("/transforms/does-not-exist/ask", json={"question": "Anything?"})
    assert response.status_code == 404


async def test_ask_before_ingestion_finishes_is_a_409(api: tuple[TestClient, FastAPI]) -> None:
    """`prepare()` alone (no `execute()`) leaves only the placeholder dossier."""
    client, app = api
    request = TransformRequest(
        sources=[SourceInput(kind=SourceKind.text, text="Some source text.")],
        output_types=["executive_summary"],
        params=GenerationParams(),
    )
    transform_id, _jobs = await prepare(request, agents=app.state.agents, store=app.state.store)
    response = client.post(f"/transforms/{transform_id}/ask", json={"question": "What is this?"})
    assert response.status_code == 409


def test_transform_ask_streams_a_grounded_answer(
    api: tuple[TestClient, FastAPI], configs_dir: Path
) -> None:
    client, _ = api
    body = {
        "sources": [{"kind": "file", "path": _article(configs_dir)}],
        "output_types": ["executive_summary"],
    }
    posted = client.post("/transforms", json=body)
    assert posted.status_code == 202
    transform_id = posted.json()["transform_id"]

    for _ in range(400):
        if client.get(f"/transforms/{transform_id}").json()["status"] in {"SUCCEEDED", "FAILED"}:
            break
        time.sleep(0.05)

    with client.stream(
        "POST", f"/transforms/{transform_id}/ask", json={"question": "What happened here?"}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        frames = _read_sse(response)

    assert frames[-1]["event"] == "done"
    assert _answer_text(frames) == "What happened here?"


def test_qa_session_lifecycle(api: tuple[TestClient, FastAPI]) -> None:
    """A session assembled from inline text can be asked about."""
    client, _ = api
    created = client.post(
        "/qa/sessions",
        json={"sources": [{"kind": "text", "text": "The pilot trained 8,400 students."}]},
    )
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    with client.stream(
        "POST", f"/qa/sessions/{session_id}/ask", json={"question": "How many students?"}
    ) as response:
        assert response.status_code == 200
        frames = _read_sse(response)

    assert frames[-1]["event"] == "done"
    assert _answer_text(frames) == "How many students?"


async def test_qa_session_is_never_persisted_as_a_transform(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, app = api
    created = client.post(
        "/qa/sessions", json={"sources": [{"kind": "text", "text": "Some evidence."}]}
    )
    session_id = created.json()["session_id"]
    assert await app.state.store.get_dossier(session_id) is None
    assert await app.state.store.list_jobs_for_transform(session_id) == []


def test_unknown_qa_session_ask_is_a_404(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api
    response = client.post("/qa/sessions/does-not-exist/ask", json={"question": "Anything?"})
    assert response.status_code == 404


def test_qa_session_requires_at_least_one_source(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api
    response = client.post("/qa/sessions", json={"sources": []})
    assert response.status_code == 422
