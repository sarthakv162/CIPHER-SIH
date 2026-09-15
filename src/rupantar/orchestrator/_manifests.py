"""Provenance manifest emission, lifted out of runner.py to keep it under the file-size limit."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from rupantar.agents.base import ArtefactAgent
from rupantar.audit.provenance import Manifest, app_version, write_manifest
from rupantar.core.schemas import Job, TransformRequest
from rupantar.models.manager import ModelManager
from rupantar.verify.report import VerificationReport


def emit_all_manifests(
    outcomes: list[Any],
    report: VerificationReport | None,
    *,
    manager: ModelManager,
    request: TransformRequest,
    dossier_sha: str,
    operator: str,
    clock: Callable[[], datetime],
) -> None:
    """Write a provenance manifest for every succeeded job's files, once verification is known."""
    for outcome in outcomes:
        verification = report.for_manifest(outcome.agent.artefact_type) if report else None
        _emit_manifests(
            outcome.paths,
            job=outcome.job,
            agent=outcome.agent,
            manager=manager,
            request=request,
            dossier_sha=dossier_sha,
            operator=operator,
            clock=clock,
            verification=verification,
            render_warnings=outcome.render_warnings,
            panel_provenance=outcome.panel_provenance,
        )


def _emit_manifests(
    paths: list[Path],
    *,
    job: Job,
    agent: ArtefactAgent,
    manager: ModelManager,
    request: TransformRequest,
    dossier_sha: str,
    operator: str,
    clock: Callable[[], datetime],
    verification: dict[str, Any] | None = None,
    render_warnings: list[str] | None = None,
    panel_provenance: dict[str, str] | None = None,
) -> None:
    """Write a provenance manifest beside every produced file."""
    meta = manager.model_meta(job.model_key)
    params = request.params.model_dump(mode="json")
    provenance = panel_provenance or {}
    for path in paths:
        manifest = Manifest(
            source_sha256=dossier_sha,
            artefact_type=agent.artefact_type,
            artefact_format=path.suffix.lstrip("."),
            model_key=job.model_key,
            model_sha256=meta.get("sha256"),
            model_quant=str(meta.get("quant", "unknown")),
            prompt_version=agent.prompt_version,
            generation_params=params,
            created_at=job.created_at.isoformat(),
            rendered_at=clock().isoformat(),
            operator=operator,
            app_version=app_version(),
            job_id=job.id,
            transform_id=job.transform_id,
            verification=verification,
            render_warnings=render_warnings or [],
            panel_provenance=provenance.get(path.name),
        )
        write_manifest(path, manifest)
