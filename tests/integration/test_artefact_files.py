"""Artefact file listing, download and manifest routes, plus real path-traversal attempts."""

from __future__ import annotations

import json
from collections.abc import Iterator
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from rupantar.api.app import create_app
from rupantar.api.paths import resolve_job_file, safe_file_name
from rupantar.api.routes.files import get_job_file
from rupantar.core.config import Env, load_config


@pytest.fixture
def client(
    configs_dir: Path, artefacts_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """A TestClient on the stub profile with a throwaway database and no frontend build."""
    monkeypatch.setenv("RUPANTAR_STUB_COMPLETION", str(artefacts_dir))
    monkeypatch.setenv("RUPANTAR_FRONTEND_DIST", str(tmp_path / "no-such-dist"))
    config = load_config(configs_dir, env=Env(profile="test-stub", db=tmp_path / "rupantar.db"))
    with TestClient(create_app(config)) as test_client:
        yield test_client


def _run_one(test_client: TestClient, configs_dir: Path) -> dict[str, Any]:
    """Run a one-artefact transform and wait on the SSE terminal event (manifests are on disk)."""
    article = configs_dir.parent / "tests" / "fixtures" / "articles" / "ai_policy_brief.md"
    body = {
        "sources": [{"kind": "file", "path": str(article)}],
        "output_types": ["executive_summary"],
    }
    transform_id = test_client.post("/transforms", json=body).json()["transform_id"]
    with test_client.stream("GET", f"/transforms/{transform_id}/events") as stream:
        for line in stream.iter_lines():
            if line.startswith("data: ") and json.loads(line[len("data: ") :]).get("final"):
                break
    payload = dict(test_client.get(f"/transforms/{transform_id}").json())
    assert payload["status"] == "SUCCEEDED", payload
    return payload


@pytest.fixture
def run(client: TestClient, configs_dir: Path) -> tuple[TestClient, str, str, Path]:
    """A completed one-job transform: (client, transform_id, job_id, job output directory)."""
    payload = _run_one(client, configs_dir)
    job = payload["jobs"][0]
    return client, payload["transform_id"], job["id"], Path(job["artefact_path"]).parent


def _files_url(transform_id: str, job_id: str) -> str:
    return f"/transforms/{transform_id}/jobs/{job_id}/files"


def test_listing_reports_every_artefact_and_hides_the_manifests(
    run: tuple[TestClient, str, str, Path],
) -> None:
    client, transform_id, job_id, job_dir = run
    response = client.get(_files_url(transform_id, job_id))
    assert response.status_code == 200
    entries = response.json()
    names = {entry["name"] for entry in entries}
    assert names == {path.name for path in job_dir.iterdir() if ".manifest.json" not in path.name}
    assert {"executive_summary.json", "executive_summary.md"} <= names
    assert not any(name.endswith(".manifest.json") for name in names)
    for entry in entries:
        assert entry["size_bytes"] > 0
        assert entry["format"] == entry["name"].rsplit(".", 1)[1]
        assert entry["has_manifest"] is True


def test_download_serves_content_with_the_right_type(
    run: tuple[TestClient, str, str, Path],
) -> None:
    client, transform_id, job_id, job_dir = run
    for name, expected in [
        ("executive_summary.json", "application/json"),
        ("executive_summary.md", "text/markdown; charset=utf-8"),
    ]:
        response = client.get(f"{_files_url(transform_id, job_id)}/{name}")
        assert response.status_code == 200
        assert response.headers["content-type"] == expected
        assert response.content == (job_dir / name).read_bytes()


def test_download_supports_range_requests_for_video(
    run: tuple[TestClient, str, str, Path],
) -> None:
    client, transform_id, job_id, job_dir = run
    payload = b"fake-mp4-bytes-for-seeking" * 8
    (job_dir / "video_package.mp4").write_bytes(payload)
    (job_dir / "video_package.mp4.manifest.json").write_text("{}", encoding="utf-8")

    url = f"{_files_url(transform_id, job_id)}/video_package.mp4"
    whole = client.get(url)
    assert whole.status_code == 200
    assert whole.headers["content-type"] == "video/mp4"
    assert whole.headers["accept-ranges"] == "bytes"

    partial = client.get(url, headers={"Range": "bytes=10-19"})
    assert partial.status_code == 206
    assert partial.headers["content-range"] == f"bytes 10-19/{len(payload)}"
    assert partial.content == payload[10:20]


def test_manifest_returns_provenance_for_the_primary_artefact(
    run: tuple[TestClient, str, str, Path],
) -> None:
    client, transform_id, job_id, _ = run
    response = client.get(f"/transforms/{transform_id}/jobs/{job_id}/manifest")
    assert response.status_code == 200
    manifest = response.json()
    assert manifest["transform_id"] == transform_id
    assert manifest["job_id"] == job_id
    assert manifest["artefact_type"] == "executive_summary"
    assert manifest["source_sha256"]


def test_unknown_transform_job_and_cross_transform_job_all_404(
    run: tuple[TestClient, str, str, Path], configs_dir: Path
) -> None:
    client, transform_id, job_id, _ = run
    other_job_id = _run_one(client, configs_dir)["jobs"][0]["id"]
    for url in (
        _files_url("no-such-transform", job_id),
        _files_url(transform_id, "no-such-job"),
        _files_url(transform_id, other_job_id),
        f"/transforms/{transform_id}/jobs/{other_job_id}/manifest",
        f"{_files_url(transform_id, other_job_id)}/executive_summary.json",
    ):
        assert client.get(url).status_code == 404, url


def test_manifest_404s_when_none_has_been_written(
    run: tuple[TestClient, str, str, Path],
) -> None:
    client, transform_id, job_id, job_dir = run
    for manifest in job_dir.glob("*.manifest.json"):
        manifest.unlink()
    response = client.get(f"/transforms/{transform_id}/jobs/{job_id}/manifest")
    assert response.status_code == 404
    assert "provenance" in response.json()["detail"]


def test_listing_is_empty_when_the_job_wrote_nothing(
    run: tuple[TestClient, str, str, Path],
) -> None:
    client, transform_id, job_id, job_dir = run
    for path in job_dir.iterdir():
        path.unlink()
    assert client.get(_files_url(transform_id, job_id)).json() == []


PASSWD_MARKER = "root:"

# Percent-encoded separators are normalised away by httpx and by the ASGI server, so these
# never reach the handler; they are here to prove the whole stack answers 404 anyway.
NORMALISED_AWAY = [
    "../../etc/passwd",
    "..%2F..%2Fetc%2Fpasswd",
    "..%2F..%2F..%2F..%2Fetc%2Fpasswd",
    "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    "%2Fetc%2Fpasswd",
    "%2F%2Fetc%2Fpasswd",
    "....%2F%2F....%2F%2Fetc%2Fpasswd",
    "..%2Fetc%2Fpasswd%00.json",
    "%2E%2E%2Fexecutive_summary.json",
]

# These survive URL normalisation and are handed to the route as the `filename` path
# parameter, so only `resolve_job_file` stands between them and the filesystem.
REACH_THE_HANDLER = [
    ("%2e%2e", ".."),
    (".%2e", ".."),
    ("%2e%2e%5C%2e%2e%5Cetc%5Cpasswd", "..\\..\\etc\\passwd"),
    ("%2e%2e%5Cexecutive_summary.json", "..\\executive_summary.json"),
    ("executive_summary.json%00", "executive_summary.json\x00"),
    ("%00", "\x00"),
    ("executive_summary.json%00.txt", "executive_summary.json\x00.txt"),
    ("advisory%0D%0AX-Injected:%201", "advisory\r\nX-Injected: 1"),
    ("advisory%0Ax", "advisory\nx"),
    ("advisory%7Fx", "advisory\x7fx"),
]


@pytest.mark.parametrize("attack", NORMALISED_AWAY)
def test_encoded_traversal_attempts_404_and_read_nothing(
    run: tuple[TestClient, str, str, Path], attack: str
) -> None:
    client, transform_id, job_id, _ = run
    response = client.get(f"{_files_url(transform_id, job_id)}/{attack}")
    assert response.status_code == 404, (attack, response.status_code)
    assert PASSWD_MARKER not in response.text


@pytest.mark.parametrize(("attack", "decoded"), REACH_THE_HANDLER)
def test_hostile_names_that_reach_the_handler_are_rejected(
    run: tuple[TestClient, str, str, Path], attack: str, decoded: str
) -> None:
    client, transform_id, job_id, job_dir = run
    assert safe_file_name(decoded) is False
    assert resolve_job_file(job_dir, decoded) is None
    response = client.get(f"{_files_url(transform_id, job_id)}/{attack}")
    assert response.status_code == 404, (attack, response.status_code)
    assert PASSWD_MARKER not in response.text
    assert "X-Injected" not in response.headers


def test_the_handler_itself_404s_on_a_literal_traversal_filename(
    run: tuple[TestClient, str, str, Path],
) -> None:
    """Bypass URL normalisation entirely and hand the route a raw traversal path."""
    client, transform_id, job_id, _ = run
    store = client.app.state.store
    config = client.app.state.config
    for name in ("../../etc/passwd", "/etc/passwd", "..", "a\x00b"):
        with pytest.raises(HTTPException) as excinfo:
            client.portal.call(
                partial(get_job_file, transform_id, job_id, name, store=store, config=config)
            )
        assert excinfo.value.status_code == 404


def test_traversal_into_a_sibling_job_directory_404s(
    run: tuple[TestClient, str, str, Path], configs_dir: Path
) -> None:
    client, transform_id, job_id, _ = run
    other = _run_one(client, configs_dir)["jobs"][0]["id"]
    attack = f"..%2F{other}%2Fexecutive_summary.json"
    assert client.get(f"{_files_url(transform_id, job_id)}/{attack}").status_code == 404


def test_a_symlink_planted_in_the_job_directory_is_neither_listed_nor_served(
    run: tuple[TestClient, str, str, Path], tmp_path: Path
) -> None:
    client, transform_id, job_id, job_dir = run
    secret = tmp_path / "outside-secret.txt"
    secret.write_text("classified payload", encoding="utf-8")
    (job_dir / "innocent.txt").symlink_to(secret)

    listing = client.get(_files_url(transform_id, job_id)).json()
    assert "innocent.txt" not in {entry["name"] for entry in listing}

    response = client.get(f"{_files_url(transform_id, job_id)}/innocent.txt")
    assert response.status_code == 404
    assert "classified payload" not in response.text


def test_symlink_to_a_system_file_is_not_served(
    run: tuple[TestClient, str, str, Path],
) -> None:
    client, transform_id, job_id, job_dir = run
    (job_dir / "passwd.txt").symlink_to(Path("/etc/passwd"))
    response = client.get(f"{_files_url(transform_id, job_id)}/passwd.txt")
    assert response.status_code == 404
    assert PASSWD_MARKER not in response.text


def test_traversal_is_rejected_before_the_transform_is_even_known(client: TestClient) -> None:
    response = client.get("/transforms/nope/jobs/nope/files/..%2F..%2Fetc%2Fpasswd")
    assert response.status_code == 404
    assert PASSWD_MARKER not in response.text


def test_transform_routes_still_404_and_are_not_masked_by_the_spa(client: TestClient) -> None:
    response = client.get("/transforms/unknown/jobs/unknown/files")
    assert response.status_code == 404
    assert "<!doctype html" not in response.text.lower()


def test_these_routes_write_nothing_to_the_job_directory(
    run: tuple[TestClient, str, str, Path],
) -> None:
    client, transform_id, job_id, job_dir = run
    before = sorted(path.name for path in job_dir.iterdir())
    client.get(_files_url(transform_id, job_id))
    client.get(f"{_files_url(transform_id, job_id)}/executive_summary.json")
    client.get(f"/transforms/{transform_id}/jobs/{job_id}/manifest")
    client.get(f"{_files_url(transform_id, job_id)}/..%2F..%2Fetc%2Fpasswd")
    assert sorted(path.name for path in job_dir.iterdir()) == before


@pytest.fixture
def client_with_console(
    configs_dir: Path, artefacts_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """A TestClient with a built console mounted at `/`, to prove the SPA masks no API 404."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>console</title>", encoding="utf-8")
    monkeypatch.setenv("RUPANTAR_STUB_COMPLETION", str(artefacts_dir))
    monkeypatch.setenv("RUPANTAR_FRONTEND_DIST", str(dist))
    config = load_config(configs_dir, env=Env(profile="test-stub", db=tmp_path / "rupantar.db"))
    with TestClient(create_app(config)) as test_client:
        yield test_client


def test_the_console_never_masks_a_file_route_404(client_with_console: TestClient) -> None:
    assert "console" in client_with_console.get("/workspace").text
    for url in (
        "/transforms/unknown/jobs/unknown/files",
        "/transforms/unknown/jobs/unknown/files/advisory.pdf",
        "/transforms/unknown/jobs/unknown/files/..%2F..%2Fetc%2Fpasswd",
        "/transforms/unknown/jobs/unknown/files/%2e%2e",
        "/transforms/unknown/jobs/unknown/manifest",
    ):
        response = client_with_console.get(url)
        assert response.status_code == 404, url
        assert "console" not in response.text, url
