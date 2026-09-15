"""The converter's browser upload uses a separate, restricted set of file types."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rupantar.api.app import get_config
from rupantar.api.routes.convert import router as converter
from rupantar.api.routes.uploads import router as uploads


@pytest.fixture
def upload_client(tmp_path: Path):
    app = FastAPI()
    app.include_router(uploads)
    app.include_router(converter)
    app.dependency_overrides[get_config] = lambda: SimpleNamespace(db_path=tmp_path / "app.db")
    with TestClient(app) as client:
        yield client


def test_uploaded_csv_can_be_converted_without_a_client_filesystem_path(upload_client):
    response = upload_client.post(
        "/sources?filename=report.csv&purpose=conversion", content=b"name,count\nschools,120\n"
    )
    assert response.status_code == 201
    source = Path(response.json()["path"])
    result = upload_client.post(
        "/convert", json={"input_path": str(source), "src_format": "csv", "dst_format": "json"}
    )
    assert result.status_code == 200
    report = result.json()
    assert report["ok"]
    assert json.loads(Path(report["output_path"]).read_text()) == [
        {"name": "schools", "count": "120"}
    ]


def test_conversion_file_is_still_rejected_as_an_ai_source(upload_client):
    response = upload_client.post("/sources?filename=report.csv", content=b"name,count\na,1\n")
    assert response.status_code == 415


@pytest.mark.parametrize("filename", ["run.py", "run.sh", "app.exe", "library.so", "image.png"])
def test_conversion_upload_rejects_unrelated_file_types(upload_client, filename):
    response = upload_client.post(
        "/sources", params={"filename": filename, "purpose": "conversion"}, content=b"untrusted"
    )
    assert response.status_code == 415


def test_conversion_upload_preserves_existing_file(upload_client):
    first = upload_client.post("/sources?filename=report.csv&purpose=conversion", content=b"first")
    second = upload_client.post(
        "/sources?filename=report.csv&purpose=conversion", content=b"second"
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["path"] != second.json()["path"]
    assert Path(first.json()["path"]).read_bytes() == b"first"
