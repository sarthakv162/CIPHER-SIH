"""GET /transforms and GET /selfcheck: the two console routes that read, never write."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import psutil
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rupantar.api.app import create_app
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


def _run(client: TestClient, configs_dir: Path, *output_types: str) -> str:
    """Post one transform and block on its terminal SSE frame, which lands after the manifests."""
    body = {
        "sources": [{"kind": "file", "path": _article(configs_dir)}],
        "output_types": list(output_types),
    }
    transform_id: str = client.post("/transforms", json=body).json()["transform_id"]
    with client.stream("GET", f"/transforms/{transform_id}/events") as stream:
        for line in stream.iter_lines():
            if line.startswith("data: ") and json.loads(line[len("data: ") :]).get("final"):
                break
    return transform_id


def test_transforms_list_is_newest_first(
    api: tuple[TestClient, FastAPI], configs_dir: Path
) -> None:
    client, _ = api
    first = _run(client, configs_dir, "executive_summary")
    second = _run(client, configs_dir, "advisory", "x_thread")

    response = client.get("/transforms")
    assert response.status_code == 200
    rows = response.json()
    assert [row["transform_id"] for row in rows] == [second, first]
    assert rows[0]["output_types"] == ["advisory", "x_thread"]
    assert rows[0]["job_count"] == 2
    assert rows[0]["status"] in {"SUCCEEDED", "FAILED"}
    assert rows[1]["output_types"] == ["executive_summary"]
    assert "conflicts" in rows[0] and "has_verification" in rows[0]


def test_transforms_list_respects_limit(api: tuple[TestClient, FastAPI], configs_dir: Path) -> None:
    client, _ = api
    _run(client, configs_dir, "executive_summary")
    newest = _run(client, configs_dir, "linkedin_post")

    rows = client.get("/transforms", params={"limit": 1}).json()
    assert [row["transform_id"] for row in rows] == [newest]
    assert client.get("/transforms", params={"limit": 0}).status_code == 422


def test_transforms_list_is_empty_before_any_run(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api
    assert client.get("/transforms").json() == []


def test_selfcheck_returns_a_report(api: tuple[TestClient, FastAPI]) -> None:
    client, _ = api
    response = client.get("/selfcheck")
    assert response.status_code == 200
    report = response.json()
    assert report["result"] in {"PASS", "FAIL"}
    assert isinstance(report["ok"], bool)
    numbers = [check["number"] for check in report["checks"]]
    for expected in ("1", "2", "3", "4", "4b", "5", "6", "7", "8"):
        assert expected in numbers, f"missing check {expected}"


def test_selfcheck_default_loads_no_model(api: tuple[TestClient, FastAPI]) -> None:
    """INV-1/2/7: a casual page load must not spawn a model process in the API process."""
    client, app = api
    before = {child.pid for child in psutil.Process().children(recursive=True)}

    report = client.get("/selfcheck").json()

    after = {child.pid for child in psutil.Process().children(recursive=True)}
    assert after - before == set()
    assert not [row for row in app.state.manager.status() if row["state"] == "READY"]
    check_five = next(c for c in report["checks"] if c["number"] == "5")
    assert check_five["level"] == "ok"
    assert "skipped" in check_five["detail"]
    check_offload = next(c for c in report["checks"] if c["number"] == "4b")
    assert "skipped" in check_offload["detail"]


def test_selfcheck_accepts_the_load_model_flag(api: tuple[TestClient, FastAPI]) -> None:
    """The flag is routable; on the stub profile the checks still short-circuit."""
    client, _ = api
    response = client.get("/selfcheck", params={"fast": "true", "load_model": "true"})
    assert response.status_code == 200
    assert "checks" in response.json()


def test_selfcheck_refuses_the_model_probe_while_a_model_is_resident(
    api: tuple[TestClient, FastAPI],
) -> None:
    """The probe builds its own ModelManager, so it must be refused, never risked (INV-2)."""
    client, app = api

    class _Resident:
        def status(self) -> list[dict[str, object]]:
            return [{"key": "brain", "state": "READY"}]

    original = app.state.manager
    app.state.manager = _Resident()
    try:
        response = client.get("/selfcheck", params={"load_model": True})
        assert response.status_code == 409
        assert "two heavy models must never be resident" in response.json()["detail"]
        # The default call is always allowed: it starts nothing.
        assert client.get("/selfcheck").status_code == 200
    finally:
        app.state.manager = original
