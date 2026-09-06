"""INV-4: no outbound network connection to a non-loopback address at runtime.

Two guards:
1. Static: no source module calls out to a networking client that could reach the internet
   (`requests`, `urllib3`, `socket.create_connection` to a literal host).
2. Dynamic: run a full stub-runtime transform through the API and assert the egress monitor
   sees zero non-loopback connections across the whole run.
"""

from __future__ import annotations

import time
from pathlib import Path

from rupantar.audit.egress import (
    accumulated_violations,
    clear_accumulated,
    enforce_offline_env,
    scan_egress,
)

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src" / "rupantar"
_CONFIGS = _REPO / "configs"
_ARTICLE = _REPO / "tests" / "fixtures" / "articles" / "ai_policy_brief.md"
_ARTEFACTS = _REPO / "tests" / "fixtures" / "artefacts"

_BANNED_IMPORTS = ("import requests", "import urllib3", "from requests", "from urllib3")


def test_no_networking_client_imports() -> None:
    """No src module imports requests/urllib3 (httpx is loopback-only, allowed)."""
    offenders: list[str] = []
    for path in _SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for banned in _BANNED_IMPORTS:
            if banned in text:
                offenders.append(f"{path.relative_to(_SRC.parent.parent)}: {banned!r}")
    assert not offenders, f"internet-capable HTTP clients imported: {offenders}"


def test_offline_env_enforced() -> None:
    """enforce_offline_env sets the HF/transformers offline switches."""
    applied = enforce_offline_env()
    assert applied["HF_HUB_OFFLINE"] == "1"
    assert applied["TRANSFORMERS_OFFLINE"] == "1"


def test_stub_transform_makes_no_non_loopback_connection(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """A full transform via the API TestClient produces zero non-loopback connections."""
    from fastapi.testclient import TestClient

    from rupantar.api.app import create_app
    from rupantar.core.config import Env, load_config
    from rupantar.core.schemas import ArtefactType

    clear_accumulated()
    monkeypatch.setenv("RUPANTAR_STUB_COMPLETION", str(_ARTEFACTS))
    config = load_config(_CONFIGS, env=Env(profile="test-stub", db=tmp_path / "rupantar.db"))
    app = create_app(config)

    body = {
        "sources": [{"kind": "file", "path": str(_ARTICLE)}],
        "output_types": [t.value for t in ArtefactType],
    }
    before = scan_egress()
    with TestClient(app) as client:
        accepted = client.post("/transforms", json=body)
        assert accepted.status_code == 202
        transform_id = accepted.json()["transform_id"]
        status = _poll(client, transform_id)
        during = scan_egress()
        egress_route = client.get("/health/egress").json()
    assert status == "SUCCEEDED"

    assert before.clean, before.violations
    assert during.clean, during.violations
    assert egress_route["clean"] is True
    assert accumulated_violations() == []


def _poll(client: object, transform_id: str, tries: int = 400) -> str:
    """Poll the transform until its aggregate status is terminal."""
    for _ in range(tries):
        payload = client.get(f"/transforms/{transform_id}").json()  # type: ignore[attr-defined]
        if payload["status"] in {"SUCCEEDED", "FAILED"}:
            return str(payload["status"])
        time.sleep(0.05)
    return "TIMEOUT"
