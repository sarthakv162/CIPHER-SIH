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


@models_app.command("status")
def models_status() -> None:
    """Show resident models and their memory use (phase 1)."""
    _stub("models status", 1)


if __name__ == "__main__":
    app()
