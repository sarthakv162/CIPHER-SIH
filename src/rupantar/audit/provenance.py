"""Provenance manifests: every artefact file on disk gets a sibling .manifest.json (INV-5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

_MANIFEST_SUFFIX = ".manifest.json"


class Manifest(BaseModel):
    """The provenance record written beside every artefact file."""

    model_config = ConfigDict(extra="forbid")

    source_sha256: str
    artefact_type: str
    artefact_format: str
    model_key: str
    model_sha256: str | None
    model_quant: str
    prompt_version: str
    generation_params: dict[str, Any]
    created_at: str
    rendered_at: str
    operator: str
    app_version: str
    job_id: str
    transform_id: str


def manifest_path(artefact_path: Path) -> Path:
    """The sibling manifest path for an artefact file (`x.docx` -> `x.docx.manifest.json`)."""
    return artefact_path.with_name(artefact_path.name + _MANIFEST_SUFFIX)


def write_manifest(artefact_path: Path, manifest: Manifest) -> Path:
    """Write `manifest` beside `artefact_path` and return the manifest path."""
    target = manifest_path(artefact_path)
    target.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return target


def is_manifest(path: Path) -> bool:
    """True when `path` is itself a manifest file."""
    return path.name.endswith(_MANIFEST_SUFFIX)
