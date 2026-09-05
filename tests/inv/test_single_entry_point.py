"""INV-7: ModelManager.acquire() is the only code path that starts a model process.

Process spawning must be confined to src/rupantar/models/runtime_*.py. Every other module
under src/rupantar/ is scanned for subprocess / os.spawn / create_subprocess / multiprocessing.
"""

from __future__ import annotations

import re
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "rupantar"

_FORBIDDEN = [
    re.compile(r"\bsubprocess\b"),
    re.compile(r"\bPopen\b"),
    re.compile(r"\bos\.spawn"),
    re.compile(r"\bos\.posix_spawn"),
    re.compile(r"create_subprocess_(exec|shell)"),
    re.compile(r"\bmultiprocessing\b"),
]


def _is_runtime_module(path: Path) -> bool:
    return path.name.startswith("runtime_")


def test_only_runtime_modules_spawn_processes() -> None:
    offenders: list[str] = []
    for path in _SRC.rglob("*.py"):
        if _is_runtime_module(path):
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in _FORBIDDEN:
            if pattern.search(text):
                offenders.append(f"{path.relative_to(_SRC)} :: /{pattern.pattern}/")
    assert not offenders, f"process spawning found outside runtime_*.py: {offenders}"


def test_manager_exposes_acquire_as_the_entry_point() -> None:
    from rupantar.models.manager import ModelManager

    assert hasattr(ModelManager, "acquire")
    assert hasattr(ModelManager, "obtain")


def test_runtime_modules_do_spawn() -> None:
    runtime_text = "\n".join(
        p.read_text(encoding="utf-8") for p in _SRC.glob("models/runtime_*.py")
    )
    assert "subprocess" in runtime_text
