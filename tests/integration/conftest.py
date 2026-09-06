"""Integration fixtures: repository paths for config and fixture files."""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Repository root directory."""
    return _REPO


@pytest.fixture(scope="session")
def configs_dir(repo_root: Path) -> Path:
    """The repository configs/ directory."""
    return repo_root / "configs"
