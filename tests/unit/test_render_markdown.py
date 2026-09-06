"""Markdown renderer: every artefact fixture produces non-empty Markdown with its title."""

from __future__ import annotations

from pathlib import Path

import pytest

from rupantar.core.artefacts import ARTEFACT_MODELS
from rupantar.render.base import render
from rupantar.render.markdown import render_md

_TYPES = sorted(ARTEFACT_MODELS)


@pytest.mark.parametrize("artefact_type", _TYPES)
def test_markdown_contains_title(artefact_type: str, artefacts_dir: Path, tmp_path: Path) -> None:
    """render_md writes a file whose first heading is the artefact title."""
    model = ARTEFACT_MODELS[artefact_type]
    artefact = model.model_validate_json((artefacts_dir / f"{artefact_type}.json").read_text())
    out = tmp_path / f"{artefact_type}.md"
    render_md(artefact, out)
    text = out.read_text(encoding="utf-8")
    assert text.startswith(f"# {artefact.title}")
    assert len(text) > 80


@pytest.mark.parametrize("artefact_type", _TYPES)
def test_dispatch_writes_markdown(artefact_type: str, artefacts_dir: Path, tmp_path: Path) -> None:
    """base.render always includes a Markdown file for every artefact type."""
    model = ARTEFACT_MODELS[artefact_type]
    artefact = model.model_validate_json((artefacts_dir / f"{artefact_type}.json").read_text())
    paths = render(artefact, tmp_path)
    md = [p for p in paths if p.suffix == ".md"]
    assert md and md[0].read_text(encoding="utf-8").strip()
