"""Progress reporting: how a running Transform tells an observer what just happened.

The orchestrator knows nothing about who is listening. It calls a `ProgressSink` — a plain
non-blocking callable — and keeps going even if the sink raises.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from rupantar.core.schemas import Job
from rupantar.verify.report import VerificationReport

ProgressSink = Callable[[str, dict[str, Any]], None]

_log = logging.getLogger("rupantar.orchestrator.progress")


def notify(sink: ProgressSink | None, name: str, data: dict[str, Any]) -> None:
    """Send one event to the sink; a broken observer must never fail the transform."""
    if sink is None:
        return
    try:
        sink(name, data)
    except Exception as exc:  # noqa: BLE001 - an observer failure is not a job failure
        _log.debug("progress sink rejected %s event: %s", name, exc)


def job_payload(job: Job) -> dict[str, Any]:
    """The wire shape of one job status transition."""
    return {
        "job_id": job.id,
        "transform_id": job.transform_id,
        "artefact_type": job.artefact_type.value,
        "model_key": job.model_key,
        "status": job.status.value,
        "updated_at": job.updated_at.isoformat(),
        "artefact_path": job.artefact_path,
        "error": job.error,
    }


def token_payload(job: Job, delta: str) -> dict[str, Any]:
    """The wire shape of one generation token delta, attributed to its job."""
    return {
        "job_id": job.id,
        "transform_id": job.transform_id,
        "artefact_type": job.artefact_type.value,
        "delta": delta,
    }


def delta_sink(job: Job, sink: ProgressSink | None) -> Callable[[str], None] | None:
    """A per-job token-delta callback, or None so the CLI keeps printing to stdout."""
    if sink is None:
        return None
    return lambda delta: notify(sink, "token", token_payload(job, delta))


def verification_payload(transform_id: str, report: VerificationReport) -> dict[str, Any]:
    """The wire shape of a landed verification report; `ok=False` means it did not finish."""
    line = report.summarise() if report.ok else (report.warnings[0] if report.warnings else "")
    return {
        "transform_id": transform_id,
        "ok": report.ok,
        "line": line,
        "disclaimer": report.disclaimer,
        "summary": report.summary.model_dump(),
        "warnings": report.warnings,
        "conflicts": [r.model_dump() for r in report.relations if r.kind == "CONFLICT"],
    }


def transform_payload(transform_id: str, jobs: list[Job], *, final: bool) -> dict[str, Any]:
    """The wire shape of a transform-level status change; `final` closes an SSE stream."""
    statuses = [job.status.value for job in jobs]
    return {
        "transform_id": transform_id,
        "status": aggregate_status(statuses),
        "final": final,
        "jobs": {job.id: job.status.value for job in jobs},
    }


def aggregate_status(statuses: list[str]) -> str:
    """Fold job statuses into one transform status, matching GET /transforms/{id}."""
    unique = set(statuses)
    if "RUNNING" in unique:
        return "RUNNING"
    if "PENDING" in unique:
        return "PENDING"
    if unique == {"SUCCEEDED"}:
        return "SUCCEEDED"
    return "FAILED"
