"""Pure helpers lifted out of `runner.py` to keep that module under the file-size limit."""

from __future__ import annotations

from pathlib import Path

from rupantar.core.artefacts import ArtefactBase
from rupantar.core.errors import ConfigError
from rupantar.core.schemas import Job, SourceInput, SourceKind


def client_read_timeout(verification_params: dict[str, object] | None) -> float:
    """HTTP read timeout for a model group's client, sized so `run_verification`'s own
    asyncio budget expires before an opaque lower-level httpx ReadTimeout can."""
    budget = float((verification_params or {}).get("timeout_seconds", 0))  # type: ignore[arg-type]
    return max(300.0, budget + 30.0)


def consecutive_runs(jobs: list[Job]) -> list[list[Job]]:
    """Split an ordered job list into maximal runs sharing one model_key."""
    runs: list[list[Job]] = []
    for job in jobs:
        if runs and runs[-1][0].model_key == job.model_key:
            runs[-1].append(job)
        else:
            runs.append([job])
    return runs


def write_artefact(out_dir: Path, artefact_type: str, artefact: ArtefactBase) -> str:
    """Write the validated artefact JSON (pretty) and return its path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{artefact_type}.json"
    path.write_text(artefact.model_dump_json(indent=2, by_alias=True), encoding="utf-8")
    return str(path)


def validate_sources(sources: list[SourceInput]) -> None:
    """Raise ConfigError naming the first file source whose path is not on disk."""
    for source in sources:
        if source.kind is SourceKind.file and not Path(source.path or "").is_file():
            raise ConfigError(f"source file not found: {source.path}", path=str(source.path))
