"""Provenance manifests: every artefact file on disk gets a sibling .manifest.json (INV-5)."""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from rupantar.core.errors import ReleaseError

_MANIFEST_SUFFIX = ".manifest.json"


def app_version() -> str:
    """The installed rupantar distribution version, or 'unknown' outside an installed package."""
    try:
        return _pkg_version("rupantar")
    except PackageNotFoundError:
        return "unknown"


class Release(BaseModel):
    """Operator acknowledgement of a verification finding on one artefact."""

    model_config = ConfigDict(extra="forbid")

    released_by: str
    released_at: str
    acknowledged_claim_ids: list[str] = Field(default_factory=list)
    acknowledged_relations: list[str] = Field(default_factory=list)
    note: str = ""


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
    verification: dict[str, Any] | None = None
    release: Release | None = None
    render_warnings: list[str] = Field(default_factory=list)


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


def read_manifest(manifest_file: Path) -> dict[str, Any]:
    """Load a manifest file as a raw dict, raising ReleaseError when it is missing or unreadable."""
    if not manifest_file.is_file():
        raise ReleaseError(f"no manifest at {manifest_file}; the artefact was never provenanced")
    try:
        data: Any = json.loads(manifest_file.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ReleaseError(f"manifest {manifest_file} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ReleaseError(f"manifest {manifest_file} is not a JSON object; regenerate it")
    return data


def record_release(manifest_file: Path, release: Release) -> dict[str, Any]:
    """Stamp `release` into an existing manifest, preserving every field already on disk."""
    merged = {**read_manifest(manifest_file), "release": release.model_dump(mode="json")}
    try:
        Manifest.model_validate(merged)
    except ValidationError as exc:
        raise ReleaseError(
            f"manifest {manifest_file} would become invalid: {exc}; regenerate the artefact"
        ) from exc
    manifest_file.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return merged
