"""General-format writers: each consumes list[dict] and returns warnings."""

from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml

Record = dict[str, Any]


def columns(rows: list[Record]) -> list[str]:
    """First-seen union of keys across every row, preserving discovery order."""
    seen: list[str] = []
    for row in rows:
        for key in row:
            if key not in seen:
                seen.append(key)
    return seen


def _text(value: Any) -> str:
    """Render a cell value as a string, mapping None to the empty string."""
    return "" if value is None else str(value)


def _ordered(rows: list[Record], cols: list[str]) -> list[Record]:
    """Re-key every row into the shared column order, dropping absent keys."""
    return [{col: row[col] for col in cols if col in row} for row in rows]


def _write_delimited(rows: list[Record], path: Path, delimiter: str) -> list[str]:
    """Write csv/tsv with the shared column order as the header row."""
    cols = columns(rows)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=delimiter)
        writer.writerow(cols)
        for row in rows:
            writer.writerow([_text(row.get(col, "")) for col in cols])
    return []


def write_csv(rows: list[Record], path: Path, opts: dict[str, Any]) -> list[str]:
    """Write rows as a comma-separated file."""
    return _write_delimited(rows, path, ",")


def write_tsv(rows: list[Record], path: Path, opts: dict[str, Any]) -> list[str]:
    """Write rows as a tab-separated file."""
    return _write_delimited(rows, path, "\t")


def write_json(rows: list[Record], path: Path, opts: dict[str, Any]) -> list[str]:
    """Write rows as a pretty-printed JSON array of objects in shared column order."""
    payload = _ordered(rows, columns(rows))
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return []


def write_jsonl(rows: list[Record], path: Path, opts: dict[str, Any]) -> list[str]:
    """Write one compact JSON object per line in shared column order."""
    payload = _ordered(rows, columns(rows))
    with path.open("w", encoding="utf-8") as handle:
        for row in payload:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return []


def write_yaml(rows: list[Record], path: Path, opts: dict[str, Any]) -> list[str]:
    """Write rows as a YAML list of mappings, key order preserved."""
    payload = _ordered(rows, columns(rows))
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return []


def write_xml(rows: list[Record], path: Path, opts: dict[str, Any]) -> list[str]:
    """Write <rows><row><col name="k">v</col></row></rows>, round-trippable by read_xml."""
    cols = columns(rows)
    root = ET.Element("rows")
    for row in rows:
        row_elem = ET.SubElement(root, "row")
        for col in cols:
            if col in row:
                col_elem = ET.SubElement(row_elem, "col", name=col)
                col_elem.text = _text(row[col])
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return []


def write_xlsx(rows: list[Record], path: Path, opts: dict[str, Any]) -> list[str]:
    """Write rows to a single sheet named 'data', header first."""
    import openpyxl

    cols = columns(rows)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "data"
    sheet.append(cols)
    for row in rows:
        sheet.append([_text(row.get(col, "")) for col in cols])
    workbook.save(path)
    return []


def write_parquet(rows: list[Record], path: Path, opts: dict[str, Any]) -> list[str]:
    """Write rows to Parquet with every column typed as string (round-trip fidelity)."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    cols = columns(rows)
    data = {col: [_text(row.get(col, "")) for row in rows] for col in cols}
    table = pa.table(data) if cols else pa.table({"_empty": []})
    pq.write_table(table, path)
    return []
