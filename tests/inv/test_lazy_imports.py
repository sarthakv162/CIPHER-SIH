"""INV-3: every renderer and converter imports its heavy dependency inside the function.

AST-scan each module under src/rupantar/render/ and src/rupantar/parivartan/ (the latter
does not exist until phase 5 and is skipped when absent). A module-level `import` of any
heavy rendering/conversion library is a build failure.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src" / "rupantar"
_SCAN_DIRS = ("render", "parivartan", "ingest")

_HEAVY = {
    "docx",
    "pptx",
    "fpdf",
    "jinja2",
    "reportlab",
    "weasyprint",
    "cairosvg",
    "pandas",
    "openpyxl",
    "pyarrow",
    "pypdf",
    "pymupdf",
    "selectolax",
    "av",
    "numpy",
    "PIL",
}


def _module_level_imports(tree: ast.Module) -> set[str]:
    """Top-level package names imported at module scope."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_render_dir_is_scanned() -> None:
    """Guard against the scan silently covering nothing."""
    assert (_SRC / "render").is_dir()


def test_heavy_render_and_converter_imports_are_lazy() -> None:
    """No module under render/ or parivartan/ imports a heavy library at module scope."""
    offenders: list[str] = []
    for name in _SCAN_DIRS:
        directory = _SRC / name
        if not directory.is_dir():
            continue
        for path in directory.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            hits = _module_level_imports(tree) & _HEAVY
            if hits:
                offenders.append(f"{path.relative_to(_REPO)}: {sorted(hits)}")
    assert not offenders, "module-level heavy imports found:\n" + "\n".join(offenders)
