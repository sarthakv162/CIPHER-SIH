"""Safe resolution of operator-supplied file names inside one job's output directory.

`{filename}` in the artefact routes is attacker-controlled. Everything here is pure and
returns `None` on rejection so the caller can answer 404 without confirming existence.
"""

from __future__ import annotations

import stat
from pathlib import Path

from rupantar.audit.provenance import is_manifest

_SEPARATORS = ("/", "\\")
_RESERVED_NAMES = frozenset({"", ".", ".."})


def safe_file_name(name: str) -> bool:
    """True when `name` is a bare, non-traversing, control-character-free file name."""
    if name in _RESERVED_NAMES:
        return False
    if any(character < " " or character == "\x7f" for character in name):
        return False
    if any(separator in name for separator in _SEPARATORS):
        return False
    candidate = Path(name)
    return not candidate.is_absolute() and not candidate.drive


def resolve_job_file(job_dir: Path, name: str) -> Path | None:
    """Real path of `name` directly inside `job_dir`, or None when unsafe or not a regular file.

    Resolution is done with real paths on both sides, so a symlink planted inside `job_dir`
    that points outside it fails the containment check rather than being followed.
    """
    if not safe_file_name(name):
        return None
    try:
        base = job_dir.resolve(strict=True)
        candidate = (base / name).resolve(strict=True)
    except (OSError, ValueError, RuntimeError):
        return None
    if not base.is_dir() or candidate.parent != base:
        return None
    try:
        info = candidate.lstat()
    except (OSError, ValueError):
        return None
    return candidate if stat.S_ISREG(info.st_mode) else None


def job_files(job_dir: Path) -> list[Path]:
    """Every regular non-manifest file directly inside `job_dir`, sorted by name.

    Symlinks are omitted: they are never written by a renderer, and a planted one must not
    appear as a downloadable artefact.
    """
    try:
        entries = sorted(job_dir.iterdir(), key=lambda path: path.name)
    except (OSError, ValueError):
        return []
    return [path for path in entries if _is_plain_file(path) and not is_manifest(path)]


def _is_plain_file(path: Path) -> bool:
    """True when `path` is a regular file and not a symlink."""
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except (OSError, ValueError):
        return False
