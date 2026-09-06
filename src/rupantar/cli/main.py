"""Typer CLI skeleton. Every command is a stub until its owning phase lands."""

from __future__ import annotations

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
    """Turn a source file into a communication artefact."""
    import asyncio

    job = asyncio.run(_transform(text, output, profile, stream, out_dir))
    if job.status.value == "FAILED":
        typer.echo(f"FAILED: {job.error}")
        raise typer.Exit(1)
    typer.echo(job.artefact_path)


async def _transform(
    text: Path, output: str, profile: str | None, stream: bool, out_dir: Path
) -> Job:
    """Load config, build the manager and agents, and run one single-job transform."""
    from rupantar.agents.loader import load_agents
    from rupantar.core.config import Env, load_config
    from rupantar.core.schemas import ArtefactType, SourceInput, SourceKind, TransformRequest
    from rupantar.core.store import Store
    from rupantar.models.manager import ModelManager
    from rupantar.models.registry import Registry
    from rupantar.orchestrator.runner import run_single

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
            return await run_single(
                request,
                manager=manager,
                agents=agents,
                store=store,
                out_root=out_dir,
                stream=stream,
            )
    finally:
        await store.close()


@app.command()
def convert() -> None:
    """Convert between data and cyber formats via Parivartan (phase 5)."""
    _stub("convert", 5)


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
