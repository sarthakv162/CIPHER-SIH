"""Typer CLI skeleton. Every command is a stub until its owning phase lands."""

from __future__ import annotations

import typer

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
def transform() -> None:
    """Turn sources into communication artefacts (phase 2+)."""
    _stub("transform", 2)


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
