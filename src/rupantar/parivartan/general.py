"""The general tabular matrix: every reader can feed every writer via a list[dict]."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from rupantar.parivartan import _readers, _writers

Reader = Callable[[Path, dict[str, Any]], tuple[list[dict[str, Any]], list[str]]]
Writer = Callable[[list[dict[str, Any]], Path, dict[str, Any]], list[str]]

READERS: dict[str, Reader] = {
    "csv": _readers.read_csv,
    "tsv": _readers.read_tsv,
    "json": _readers.read_json,
    "jsonl": _readers.read_jsonl,
    "yaml": _readers.read_yaml,
    "xml": _readers.read_xml,
    "xlsx": _readers.read_xlsx,
    "parquet": _readers.read_parquet,
}

WRITERS: dict[str, Writer] = {
    "csv": _writers.write_csv,
    "tsv": _writers.write_tsv,
    "json": _writers.write_json,
    "jsonl": _writers.write_jsonl,
    "yaml": _writers.write_yaml,
    "xml": _writers.write_xml,
    "xlsx": _writers.write_xlsx,
    "parquet": _writers.write_parquet,
}

NOTES: dict[str, str] = {
    "parquet": "all columns written as strings for round-trip fidelity",
    "xml": "shape <rows><row><col name=k>v</col></row></rows>",
}
