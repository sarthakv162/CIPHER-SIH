"""INV-1: No ML model is ever loaded inside the API process.

Static enforcement: no module under src/rupantar/ may import an in-process model
runtime (torch, transformers, llama_cpp, ctranslate2, faster_whisper, onnxruntime)
at module scope. Models run only as child processes spawned by models/runtime_*.py.
The dynamic version (assert the running API process never loads a model) lands when
the api/ package exists; until then the import scan is the guard.
"""

from __future__ import annotations

import ast
import sys
import time
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src" / "rupantar"
_CONFIGS = _REPO / "configs"
_ARTICLE = _REPO / "tests" / "fixtures" / "articles" / "ai_policy_brief.md"
_ARTEFACTS = _REPO / "tests" / "fixtures" / "artefacts"

_RUNTIME_MODULES = {
    "torch",
    "transformers",
    "llama_cpp",
    "ctranslate2",
    "faster_whisper",
    "onnxruntime",
}

_FORBIDDEN = {
    "torch",
    "transformers",
    "llama_cpp",
    "ctranslate2",
    "faster_whisper",
    "onnxruntime",
    "sentence_transformers",
}


def _module_level_imports(tree: ast.Module) -> set[str]:
    """Return the set of top-level package names imported at module scope."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_no_inprocess_model_imports() -> None:
    """No src module imports an in-process model runtime at module scope."""
    offenders: list[str] = []
    for path in _SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        hits = _module_level_imports(tree) & _FORBIDDEN
        if hits:
            offenders.append(f"{path.relative_to(_SRC.parent.parent)}: {sorted(hits)}")
    assert not offenders, "in-process model imports found:\n" + "\n".join(offenders)


def test_api_process_loads_no_model_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Drive a full transform through the API and confirm no model runtime module got imported."""
    from fastapi.testclient import TestClient

    from rupantar.api.app import create_app
    from rupantar.core.config import Env, load_config
    from rupantar.core.schemas import ArtefactType

    monkeypatch.setenv("RUPANTAR_STUB_COMPLETION", str(_ARTEFACTS))
    config = load_config(_CONFIGS, env=Env(profile="test-stub", db=tmp_path / "rupantar.db"))
    app = create_app(config)

    body = {
        "sources": [{"kind": "file", "path": str(_ARTICLE)}],
        "output_types": [t.value for t in ArtefactType],
    }
    with TestClient(app) as client:
        accepted = client.post("/transforms", json=body)
        assert accepted.status_code == 202
        transform_id = accepted.json()["transform_id"]
        status = _poll_terminal(client, transform_id)
    assert status == "SUCCEEDED"

    leaked = _RUNTIME_MODULES & set(sys.modules)
    assert not leaked, f"API process imported model runtime modules: {sorted(leaked)}"


def _poll_terminal(client: object, transform_id: str, tries: int = 200) -> str:
    """Poll GET /transforms/{id} until the aggregate status is terminal."""
    for _ in range(tries):
        payload = client.get(f"/transforms/{transform_id}").json()  # type: ignore[attr-defined]
        if payload["status"] in {"SUCCEEDED", "FAILED"}:
            return str(payload["status"])
        time.sleep(0.05)
    return "TIMEOUT"
