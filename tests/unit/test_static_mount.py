"""Static console mount: inert without a build, SPA fallback with one, never masking the API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rupantar.api.static import DIST_ENV, default_dist_dir, mount_frontend


def _api_app() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/transforms/{transform_id}")
    async def transform(transform_id: str) -> dict[str, str]:
        return {"transform_id": transform_id}

    return app


def _build_dist(root: Path) -> Path:
    dist = root / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>console</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("export const x = 1;\n", encoding="utf-8")
    return dist


def test_mount_is_a_no_op_when_dist_is_absent(tmp_path: Path) -> None:
    app = _api_app()
    before = len(app.routes)
    assert mount_frontend(app, tmp_path / "dist") is False
    assert len(app.routes) == before
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/").status_code == 404


def test_mount_is_a_no_op_when_dist_exists_but_has_no_index(tmp_path: Path) -> None:
    (tmp_path / "dist").mkdir()
    assert mount_frontend(_api_app(), tmp_path / "dist") is False


def test_index_and_assets_are_served_when_dist_is_built(tmp_path: Path) -> None:
    app = _api_app()
    assert mount_frontend(app, _build_dist(tmp_path)) is True
    with TestClient(app) as client:
        assert "console" in client.get("/").text
        assert client.get("/assets/app.js").status_code == 200


def test_unknown_non_api_path_falls_back_to_index_html(tmp_path: Path) -> None:
    app = _api_app()
    mount_frontend(app, _build_dist(tmp_path))
    with TestClient(app) as client:
        response = client.get("/workspace/run/abc123")
        assert response.status_code == 200
        assert "console" in response.text


def test_api_routes_still_win_over_the_spa_fallback(tmp_path: Path) -> None:
    app = _api_app()
    mount_frontend(app, _build_dist(tmp_path))
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/transforms/t1").json() == {"transform_id": "t1"}


def test_unknown_api_path_404s_instead_of_returning_html(tmp_path: Path) -> None:
    app = _api_app()
    mount_frontend(app, _build_dist(tmp_path))
    with TestClient(app) as client:
        response = client.get("/transforms/t1/nope/deeper")
        assert response.status_code == 404
        assert "console" not in response.text


def test_default_dist_dir_prefers_the_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(DIST_ENV, raising=False)
    assert default_dist_dir(tmp_path / "configs") == tmp_path / "frontend" / "dist"
    monkeypatch.setenv(DIST_ENV, str(tmp_path / "elsewhere"))
    assert default_dist_dir(tmp_path / "configs") == tmp_path / "elsewhere"
