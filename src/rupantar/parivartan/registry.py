"""Converter registry: bespoke converters plus the general reader x writer matrix."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rupantar.core.errors import ConversionError

BespokeFn = Callable[[Path, Path, dict[str, Any]], tuple[int, list[str]]]


@dataclass(frozen=True)
class ConversionReport:
    """Outcome of one convert() call: row count, warnings, and where the output landed."""

    src_format: str
    dst_format: str
    rows: int
    warnings: list[str]
    output_path: str | None
    duration_seconds: float
    ok: bool


@dataclass(frozen=True)
class _Bespoke:
    """A registered format-specific converter with its catalogue metadata."""

    fn: BespokeFn
    label: str
    notes: str


_BESPOKE: dict[tuple[str, str], _Bespoke] = {}


def register(
    src: str, dst: str, *, label: str, notes: str = ""
) -> Callable[[BespokeFn], BespokeFn]:
    """Register a bespoke converter fn (in_path, out_path, opts) -> (rows_written, warnings)."""

    def decorate(fn: BespokeFn) -> BespokeFn:
        _BESPOKE[(src, dst)] = _Bespoke(fn=fn, label=label, notes=notes)
        return fn

    return decorate


def _ensure_converters() -> None:
    """Import the modules that populate the bespoke and general tables."""
    from rupantar.parivartan import cyber, general  # noqa: F401


def list_conversions() -> list[dict[str, str]]:
    """Every available (src, dst): bespoke converters plus each general reader x writer pair."""
    _ensure_converters()
    from rupantar.parivartan import general

    out: list[dict[str, str]] = []
    for (src, dst), bespoke in sorted(_BESPOKE.items()):
        out.append({"src": src, "dst": dst, "label": bespoke.label, "notes": bespoke.notes})
    for src in sorted(general.READERS):
        for dst in sorted(general.WRITERS):
            out.append(
                {
                    "src": src,
                    "dst": dst,
                    "label": f"{src} -> {dst}",
                    "notes": general.NOTES.get(dst, ""),
                }
            )
    return out


def convert(
    in_path: Path,
    src: str,
    dst: str,
    out_path: Path,
    opts: dict[str, Any] | None = None,
) -> ConversionReport:
    """Dispatch to a bespoke converter or the general matrix; never raise on bad file content."""
    _ensure_converters()
    from rupantar.parivartan import general

    options = opts or {}
    started = time.monotonic()

    if not in_path.exists():
        return ConversionReport(
            src_format=src,
            dst_format=dst,
            rows=0,
            warnings=[f"input not found: {in_path}"],
            output_path=None,
            duration_seconds=time.monotonic() - started,
            ok=False,
        )

    warnings: list[str] = []
    rows = 0
    bespoke = _BESPOKE.get((src, dst))
    if bespoke is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        rows, warnings = bespoke.fn(in_path, out_path, options)
    elif src in general.READERS and dst in general.WRITERS:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        records, read_warnings = general.READERS[src](in_path, options)
        warnings.extend(read_warnings)
        warnings.extend(general.WRITERS[dst](records, out_path, options))
        rows = len(records)
    else:
        raise ConversionError(f"no converter for {src!r} -> {dst!r}; see list_conversions()")

    ok = out_path.exists() and out_path.stat().st_size > 0
    return ConversionReport(
        src_format=src,
        dst_format=dst,
        rows=rows,
        warnings=warnings,
        output_path=str(out_path) if ok else None,
        duration_seconds=time.monotonic() - started,
        ok=ok,
    )
