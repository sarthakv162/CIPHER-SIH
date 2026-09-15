"""Unit coverage for render/template_registry.py: loading, lookup, and graceful absence."""

from __future__ import annotations

from pathlib import Path

import pytest

from rupantar.core.errors import ConfigError
from rupantar.render.template_registry import (
    DEFAULT_TEMPLATE,
    get_template,
    load_templates,
    manifest_path,
    template_file,
)


def test_loads_the_three_shipped_templates() -> None:
    templates = load_templates()
    ids = {t.id for t in templates}
    assert {"ntro-formal", "executive", "technical"} <= ids


def test_default_template_has_pptx_and_docx_bindings() -> None:
    spec = get_template(DEFAULT_TEMPLATE)
    assert spec is not None
    assert spec.pptx is not None
    assert spec.docx is not None
    for key in ("title_slide", "title", "bullets", "two_column", "quote", "closing"):
        assert key in spec.pptx.layouts
    for key in (
        "title",
        "heading1",
        "heading2",
        "bullet",
        "severity_banner",
        "classification_footer",
    ):
        assert key in spec.docx.styles


def test_unknown_template_id_is_none() -> None:
    assert get_template("does-not-exist") is None


def test_missing_manifest_directory_yields_no_templates(tmp_path: Path) -> None:
    assert load_templates(tmp_path) == []
    assert get_template(DEFAULT_TEMPLATE, configs_dir=tmp_path) is None


def test_malformed_manifest_yaml_raises_a_typed_error(tmp_path: Path) -> None:
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "templates.yaml").write_text("not: [valid, yaml:", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_templates(tmp_path)
    # get_template degrades the same failure to "unknown" rather than raising.
    assert get_template(DEFAULT_TEMPLATE, configs_dir=tmp_path) is None


def test_manifest_entry_missing_a_binding_still_loads(tmp_path: Path) -> None:
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "templates.yaml").write_text(
        "templates:\n  - id: deck-only\n    label: Deck Only\n    supports: [presentation]\n",
        encoding="utf-8",
    )
    spec = get_template("deck-only", configs_dir=tmp_path)
    assert spec is not None
    assert spec.pptx is None
    assert spec.docx is None


def test_manifest_and_asset_paths_are_scoped_under_configs_templates(tmp_path: Path) -> None:
    assert manifest_path(tmp_path) == tmp_path / "templates" / "templates.yaml"
    assert template_file(tmp_path, "x.potx") == tmp_path / "templates" / "x.potx"
