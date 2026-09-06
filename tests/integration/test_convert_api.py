"""API integration for the Parivartan convert routes on the stub profile."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rupantar.api.app import create_app
from rupantar.core.config import Env, load_config


@pytest.fixture
def client(configs_dir: Path, tmp_path: Path) -> Iterator[TestClient]:
    """A TestClient wired to the test-stub profile and a tmp database."""
    config = load_config(configs_dir, env=Env(profile="test-stub", db=tmp_path / "rupantar.db"))
    with TestClient(create_app(config)) as test_client:
        yield test_client


def test_conversions_lists_pairs(client: TestClient) -> None:
    """GET /conversions returns the catalogue including cyber converters."""
    payload = client.get("/conversions").json()
    pairs = {(entry["src"], entry["dst"]) for entry in payload}
    assert ("csv", "json") in pairs
    assert ("sigma", "sigma-json") in pairs


def test_convert_runs_and_reports(client: TestClient, fixtures_dir: Path) -> None:
    """POST /convert writes an output file and returns the ConversionReport."""
    body = {
        "input_path": str(fixtures_dir / "parivartan" / "clean.csv"),
        "src_format": "csv",
        "dst_format": "jsonl",
        "opts": {},
    }
    response = client.post("/convert", json=body)
    assert response.status_code == 200
    report = response.json()
    assert report["ok"] is True
    assert report["rows"] == 3
    assert Path(report["output_path"]).is_file()


def test_convert_unknown_pair_is_400(client: TestClient, fixtures_dir: Path) -> None:
    """An unsupported (src, dst) pair returns 400, not 500."""
    body = {
        "input_path": str(fixtures_dir / "parivartan" / "clean.csv"),
        "src_format": "csv",
        "dst_format": "sigma-json",
        "opts": {},
    }
    assert client.post("/convert", json=body).status_code == 400
