"""Unit tests for the provenance manifest writer and model."""

from __future__ import annotations

from pathlib import Path

from rupantar.audit.provenance import Manifest, is_manifest, manifest_path, write_manifest


def _manifest() -> Manifest:
    return Manifest(
        source_sha256="abc123",
        artefact_type="advisory",
        artefact_format="docx",
        model_key="brain",
        model_sha256=None,
        model_quant="stub",
        prompt_version="1",
        generation_params={"tone": "neutral"},
        created_at="2026-09-06T00:00:00+00:00",
        rendered_at="2026-09-06T00:01:00+00:00",
        operator="operator",
        app_version="0.0.0",
        job_id="job-1",
        transform_id="tf-1",
    )


def test_manifest_path_appends_suffix() -> None:
    """A .docx artefact yields advisory.docx.manifest.json."""
    assert manifest_path(Path("/x/advisory.docx")).name == "advisory.docx.manifest.json"


def test_write_manifest_round_trips(tmp_path: Path) -> None:
    """The written file parses back into an equal Manifest and is detected as a manifest."""
    artefact = tmp_path / "advisory.docx"
    artefact.write_bytes(b"stub")
    written = write_manifest(artefact, _manifest())
    assert written.name == "advisory.docx.manifest.json"
    assert is_manifest(written)
    assert Manifest.model_validate_json(written.read_text(encoding="utf-8")) == _manifest()
