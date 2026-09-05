"""INV-1: No ML model is ever loaded inside the API process.

Static enforcement: no module under src/rupantar/ may import an in-process model
runtime (torch, transformers, llama_cpp, ctranslate2, faster_whisper, onnxruntime)
at module scope. Models run only as child processes spawned by models/runtime_*.py.
The dynamic version (assert the running API process never loads a model) lands when
the api/ package exists; until then the import scan is the guard.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "rupantar"

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
