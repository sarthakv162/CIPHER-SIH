"""Typer CLI: transform, convert, selfcheck, and a models sub-app."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

if TYPE_CHECKING:
    from rupantar.core.schemas import Job

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
    """Set up terminal logging so the detected hardware profile is visible."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


def _stub(feature: str, phase: int) -> None:
    """Print a uniform not-implemented notice and exit cleanly."""
    typer.echo(f"{feature} is not implemented until phase {phase}")
    raise typer.Exit(code=0)


@app.command()
def transform(
    text: Annotated[
        Path,
        typer.Option(
            ..., "--text", exists=True, dir_okay=False, readable=True, help="Source text file."
        ),
    ],
    output: Annotated[
        str, typer.Option("--output", help="Artefact type(s), comma-separated.")
    ] = "executive_summary",
    profile: Annotated[
        str | None, typer.Option("--profile", help="Hardware profile override.")
    ] = None,
    stream: Annotated[
        bool, typer.Option("--stream/--no-stream", help="Stream tokens to stdout.")
    ] = False,
    out_dir: Annotated[Path, typer.Option("--out-dir", help="Output root directory.")] = Path(
        "data/outputs"
    ),
) -> None:
    """Turn a source file into one or more communication artefacts."""
    import asyncio

    jobs = asyncio.run(_transform(text, output, profile, stream, out_dir))
    failed = 0
    for job in jobs:
        if job.status.value == "FAILED":
            failed += 1
            typer.echo(f"FAILED {job.artefact_type.value}: {job.error}")
        else:
            typer.echo(job.artefact_path)
    if failed == len(jobs):
        raise typer.Exit(1)


async def _transform(
    text: Path, output: str, profile: str | None, stream: bool, out_dir: Path
) -> list[Job]:
    """Load config, build the manager and agents, and run one batch transform."""
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
        sources=[SourceInput(kind=SourceKind.file, path=str(text))],
        output_types=[ArtefactType(part.strip()) for part in output.split(",") if part.strip()],
    )
    store = Store(config.db_path)
    await store.connect()
    try:
        async with manager:
            return await run_batch(
                request,
                manager=manager,
                agents=agents,
                store=store,
                out_root=out_dir,
                stream=stream,
            )
    finally:
        await store.close()


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
def selfcheck() -> None:
    """Run the full offline system health report (phase 8)."""
    _stub("selfcheck", 8)


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
