"""Typer CLI: transform, convert, selfcheck, and a models sub-app."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

if TYPE_CHECKING:
    from rupantar.core.schemas import Job
    from rupantar.verify.report import VerificationReport

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Rupantar: offline AI content transformation engine.",
)
models_app = typer.Typer(add_completion=False, no_args_is_help=True, help="Model manager commands.")
app.add_typer(models_app, name="models")


@app.callback()
def _init(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Debug-level logging.")] = False,
) -> None:
    """Set up terminal logging and pin the process to offline mode before any work."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    from rupantar.audit.egress import enforce_offline_env

    enforce_offline_env()


@app.command()
def transform(
    text: Annotated[
        Path | None,
        typer.Option(
            "--text", exists=True, dir_okay=False, readable=True, help="Source text file."
        ),
    ] = None,
    source: Annotated[
        list[Path] | None,
        typer.Option(
            "--source",
            exists=True,
            dir_okay=False,
            readable=True,
            help="Any source file (text, image, audio, video); repeatable.",
        ),
    ] = None,
    output: Annotated[
        str, typer.Option("--output", help="Artefact type(s), comma-separated.")
    ] = "executive_summary",
    profile: Annotated[
        str | None, typer.Option("--profile", help="Hardware profile override.")
    ] = None,
    stream: Annotated[
        bool, typer.Option("--stream/--no-stream", help="Stream tokens to stdout.")
    ] = False,
    strict_airgap: Annotated[
        bool,
        typer.Option("--strict-airgap", help="Abort a job if a non-loopback connection appears."),
    ] = False,
    operator: Annotated[
        str | None,
        typer.Option("--operator", help="Who is running this job (falls back to $USER)."),
    ] = None,
    out_dir: Annotated[Path, typer.Option("--out-dir", help="Output root directory.")] = Path(
        "data/outputs"
    ),
) -> None:
    """Turn one or more source files into communication artefacts."""
    import asyncio

    paths = [*([text] if text else []), *(source or [])]
    if not paths:
        typer.echo("pass at least one --text or --source file")
        raise typer.Exit(2)
    jobs, verification_line = asyncio.run(
        _transform(paths, output, profile, stream, strict_airgap, operator, out_dir)
    )
    failed = 0
    for job in jobs:
        if job.status.value == "FAILED":
            failed += 1
            typer.echo(f"FAILED {job.artefact_type.value}: {job.error}")
        else:
            typer.echo(job.artefact_path)
    if verification_line:
        typer.echo(verification_line)
    if failed == len(jobs):
        raise typer.Exit(1)


async def _transform(
    paths: list[Path],
    output: str,
    profile: str | None,
    stream: bool,
    strict_airgap: bool,
    operator: str | None,
    out_dir: Path,
) -> tuple[list[Job], str | None]:
    """Load config, build the manager and agents, run one batch transform and its verification."""
    from rupantar.agents.loader import load_agents
    from rupantar.core.config import Env, load_config
    from rupantar.core.schemas import ArtefactType, SourceInput, SourceKind, TransformRequest
    from rupantar.core.store import Store
    from rupantar.models.manager import ModelManager
    from rupantar.models.registry import Registry
    from rupantar.orchestrator.runner import run_batch

    config = load_config(env=Env(profile=profile) if profile else Env())
    manager = ModelManager(Registry.from_config(config, verify=False), policy=config.policy)
    agents = load_agents(config.configs_dir / "agents")
    request = TransformRequest(
        sources=[SourceInput(kind=SourceKind.file, path=str(p)) for p in paths],
        output_types=[ArtefactType(part.strip()) for part in output.split(",") if part.strip()],
        operator=operator,
    )
    store = Store(config.db_path)
    await store.connect()
    try:
        async with manager:
            jobs = await run_batch(
                request,
                manager=manager,
                agents=agents,
                store=store,
                out_root=out_dir,
                stream=stream,
                strict_airgap=strict_airgap,
                operator=operator,
                verification_params=config.policy.get("verification", {}),
            )
        report = await store.get_verification_report(jobs[0].transform_id) if jobs else None
        return jobs, _verification_line(report)
    finally:
        await store.close()


def _verification_line(report: VerificationReport | None) -> str | None:
    """The one-line verification summary printed after a transform, or None if none ran."""
    if report is None:
        return None
    if report.ok:
        return f"verification: {report.summarise()}"
    reason = report.warnings[0] if report.warnings else "no report"
    return f"verification: unavailable — {reason}"


_EXT_TO_FORMAT: dict[str, str] = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".json": "json",
    ".jsonl": "jsonl",
    ".ndjson": "jsonl",
    ".xlsx": "xlsx",
    ".xml": "xml",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".parquet": "parquet",
    ".log": "cef",
    ".cef": "cef",
}
_FORMAT_TO_EXT: dict[str, str] = {
    "stix21": "json",
    "sigma-json": "json",
    "ioc-csv": "csv",
    "cef": "jsonl",
}


def _parse_opts(pairs: list[str]) -> dict[str, str]:
    """Turn --opt k=v flags into a dict."""
    parsed: dict[str, str] = {}
    for pair in pairs:
        key, _, value = pair.partition("=")
        parsed[key.strip()] = value.strip()
    return parsed


@app.command()
def convert(
    source: Annotated[
        Path, typer.Argument(exists=False, dir_okay=False, help="Source file to convert.")
    ],
    to: Annotated[str, typer.Option("--to", help="Destination format.")],
    from_: Annotated[
        str | None, typer.Option("--from", help="Source format; inferred from the extension.")
    ] = None,
    out: Annotated[Path | None, typer.Option("--out", help="Output file path.")] = None,
    opt: Annotated[
        list[str] | None, typer.Option("--opt", help="Converter option as k=v (repeatable).")
    ] = None,
) -> None:
    """Convert between data and cyber formats via Parivartan."""
    from rupantar.core.errors import ConversionError
    from rupantar.parivartan.registry import convert as run_convert

    src = from_ or _EXT_TO_FORMAT.get(source.suffix.lower())
    if src is None:
        typer.echo(f"cannot infer --from for suffix {source.suffix!r}; pass --from explicitly")
        raise typer.Exit(1)
    destination = (
        out or Path("data/outputs/conversions") / f"{source.stem}.{_FORMAT_TO_EXT.get(to, to)}"
    )
    try:
        report = run_convert(source, src, to, destination, _parse_opts(opt or []))
    except ConversionError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc
    if not report.ok and any(w.startswith("input not found") for w in report.warnings):
        for warning in report.warnings:
            typer.echo(f"warning: {warning}")
        raise typer.Exit(1)
    typer.echo(f"{report.rows} rows -> {report.output_path or destination}")
    for warning in report.warnings:
        typer.echo(f"warning: {warning}")


@app.command()
def selfcheck(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the report as JSON instead of a table.")
    ] = False,
    fast: Annotated[bool, typer.Option("--fast", help="Skip model-file SHA-256 hashing.")] = False,
    no_model: Annotated[
        bool, typer.Option("--no-model", help="Skip checks that load the brain (4b offload, 5).")
    ] = False,
) -> None:
    """Run the full offline system health report; exit non-zero when any check fails."""
    from rupantar.audit.selfcheck import run_selfcheck

    report = run_selfcheck(fast=fast, load_model=not no_model)
    typer.echo(report.model_dump_json(indent=2) if json_output else report.table())
    raise typer.Exit(report.exit_code)


def _fmt(value: object) -> str:
    """Render a table cell, showing a dash for missing values."""
    return "-" if value is None else str(value)


@models_app.command("status")
def models_status() -> None:
    """Show every registered model and its residency state in this process."""
    from rupantar.core.config import load_config
    from rupantar.models.manager import ModelManager
    from rupantar.models.registry import Registry

    config = load_config()
    manager = ModelManager(Registry.from_config(config, verify=False), policy=config.policy)
    header = f"{'KEY':<8} {'STATE':<12} {'PID':>8} {'PORT':>6} {'RSS_MB':>8} {'REF':>4}"
    typer.echo(header)
    typer.echo("-" * len(header))
    for row in manager.status():
        typer.echo(
            f"{row['key']:<8} {row['state']:<12} {_fmt(row['pid']):>8} "
            f"{_fmt(row['port']):>6} {_fmt(row['rss_mb']):>8} {row['refcount']:>4}"
        )


if __name__ == "__main__":
    app()
