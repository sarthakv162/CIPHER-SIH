"""Shared test fixtures: paths to the canonical fixture set and a tmp SQLite path."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

_FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Root of the canonical fixture set."""
    return _FIXTURES


@pytest.fixture(scope="session")
def artefacts_dir() -> Path:
    """Directory holding the seven hand-written artefact JSON examples."""
    return _FIXTURES / "artefacts"


@pytest.fixture(scope="session")
def articles_dir() -> Path:
    """Directory holding the sample source articles."""
    return _FIXTURES / "articles"


@pytest.fixture
def db_path(tmp_path: Path) -> Iterator[Path]:
    """A throwaway SQLite path under pytest's tmp_path."""
    yield tmp_path / "rupantar-test.db"
