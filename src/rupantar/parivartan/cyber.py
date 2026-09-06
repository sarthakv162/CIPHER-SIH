"""Three cyber converters: IOC CSV <-> STIX 2.1, Sigma YAML -> JSON, CEF/syslog -> JSONL."""

from __future__ import annotations

import csv
import json
import re
import uuid
from pathlib import Path
from typing import Any

import yaml

from rupantar.core.artefacts import IocType
from rupantar.parivartan.registry import register

_STIX_TS = "2020-01-01T00:00:00.000Z"

_OBJECT_PATH_BY_TYPE: dict[str, str] = {
    "ipv4": "ipv4-addr:value",
    "ipv6": "ipv6-addr:value",
    "domain": "domain-name:value",
    "url": "url:value",
    "email": "email-addr:value",
    "filename": "file:name",
    "sha256": "file:hashes.'SHA-256'",
    "md5": "file:hashes.'MD5'",
}
_TYPE_BY_OBJECT_PATH: dict[str, str] = {path: name for name, path in _OBJECT_PATH_BY_TYPE.items()}
_TYPE_BY_OBJECT_PATH["x-custom:value"] = "other"

_PATTERN_RE = re.compile(
    r"\[\s*(ipv4-addr:value|ipv6-addr:value|domain-name:value|url:value|email-addr:value"
    r"|file:name|file:hashes\.'SHA-256'|file:hashes\.'MD5'|x-custom:value)\s*=\s*'([^']*)'\s*\]"
)

_VALID_IOC_TYPES = {member.value for member in IocType}


def _pattern_for(ioc_type: str, value: str) -> tuple[str, list[str]]:
    """Build a STIX 2.1 pattern for an IOC, falling back to x-custom for unmapped types."""
    object_path = _OBJECT_PATH_BY_TYPE.get(ioc_type)
    if object_path is None:
        return (
            f"[x-custom:value = '{value}']",
            [f"ioc type {ioc_type!r} has no standard STIX object path; used x-custom"],
        )
    return f"[{object_path} = '{value}']", []


@register(
    "ioc-csv",
    "stix21",
    label="IOC CSV -> STIX 2.1 bundle",
    notes="Hand-built STIX 2.1 JSON; no stix2 library (it pulls requests, unfit for air-gap).",
)
def ioc_csv_to_stix(in_path: Path, out_path: Path, opts: dict[str, Any]) -> tuple[int, list[str]]:
    """Convert a type,value,note CSV into a STIX 2.1 bundle of indicator SDOs."""
    warnings: list[str] = []
    objects: list[dict[str, Any]] = []
    try:
        with in_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for lineno, raw in enumerate(csv.DictReader(handle), start=2):
                sdo = _indicator_from_row(raw, in_path.name, lineno, warnings)
                if sdo is not None:
                    objects.append(sdo)
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        return 0, [f"{in_path.name}: could not parse as ioc-csv: {exc}"]
    bundle = {
        "type": "bundle",
        "id": f"bundle--{opts.get('bundle_id') or uuid.uuid4()}",
        "objects": objects,
    }
    out_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return len(objects), warnings


def _indicator_from_row(
    raw: dict[str, Any], name: str, lineno: int, warnings: list[str]
) -> dict[str, Any] | None:
    """Turn one CSV row into an indicator SDO, or None (with a warning) when it has no value."""
    value = str(raw.get("value") or "").strip()
    if not value:
        warnings.append(f"{name}: row {lineno} has no value; skipped")
        return None
    ioc_type = str(raw.get("type") or "").strip().lower()
    if ioc_type not in _VALID_IOC_TYPES:
        warnings.append(f"{name}: row {lineno} unknown ioc type {ioc_type!r}; recorded as other")
        ioc_type = "other"
    pattern, pattern_warnings = _pattern_for(ioc_type, value)
    warnings.extend(pattern_warnings)
    note = str(raw.get("note") or "").strip()
    return {
        "type": "indicator",
        "spec_version": "2.1",
        "id": f"indicator--{uuid.uuid5(uuid.NAMESPACE_URL, value)}",
        "created": _STIX_TS,
        "modified": _STIX_TS,
        "name": note or value,
        "pattern": pattern,
        "pattern_type": "stix",
        "valid_from": _STIX_TS,
    }


@register(
    "stix21",
    "ioc-csv",
    label="STIX 2.1 bundle -> IOC CSV",
    notes="Parses indicator patterns back to (type, value); non-indicator SDOs skipped.",
)
def stix_to_ioc_csv(in_path: Path, out_path: Path, opts: dict[str, Any]) -> tuple[int, list[str]]:
    """Convert a STIX 2.1 bundle back into a type,value,note CSV."""
    warnings: list[str] = []
    try:
        bundle = json.loads(in_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return 0, [f"{in_path.name}: could not parse as stix21: {exc}"]
    rows: list[dict[str, str]] = []
    for obj in bundle.get("objects", []) if isinstance(bundle, dict) else []:
        row = _row_from_indicator(obj, warnings)
        if row is not None:
            rows.append(row)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["type", "value", "note"])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows), warnings


def _row_from_indicator(obj: Any, warnings: list[str]) -> dict[str, str] | None:
    """Parse one indicator SDO's pattern into a CSV row, or None with a warning."""
    if not isinstance(obj, dict) or obj.get("type") != "indicator":
        kind = obj.get("type") if isinstance(obj, dict) else type(obj).__name__
        warnings.append(f"skipped non-indicator object {kind!r}")
        return None
    match = _PATTERN_RE.search(str(obj.get("pattern", "")))
    if match is None:
        warnings.append(f"could not parse indicator pattern {obj.get('pattern')!r}; skipped")
        return None
    object_path, value = match.group(1), match.group(2)
    return {
        "type": _TYPE_BY_OBJECT_PATH.get(object_path, "other"),
        "value": value,
        "note": str(obj.get("name", "")),
    }


@register(
    "sigma",
    "sigma-json",
    label="Sigma rule YAML -> normalised JSON",
    notes="One object per YAML document; missing keys become null or []; multi-doc -> JSON array.",
)
def sigma_to_json(in_path: Path, out_path: Path, opts: dict[str, Any]) -> tuple[int, list[str]]:
    """Normalise one or more Sigma rules into a stable-keyed JSON object or array."""
    warnings: list[str] = []
    try:
        documents = list(yaml.safe_load_all(in_path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        return 0, [f"{in_path.name}: could not parse as sigma YAML: {exc}"]
    normalised = []
    for document in documents:
        if isinstance(document, dict):
            normalised.append(_normalise_sigma(document))
        elif document is not None:
            warnings.append(f"{in_path.name}: skipped a non-mapping YAML document")
    if not normalised:
        return 0, warnings or [f"{in_path.name}: no Sigma rule documents found"]
    payload: Any = normalised[0] if len(normalised) == 1 else normalised
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(normalised), warnings


def _normalise_sigma(doc: dict[str, Any]) -> dict[str, Any]:
    """Map a Sigma rule dict onto the fixed output key set."""
    raw_logsource = doc.get("logsource")
    raw_detection = doc.get("detection")
    logsource: dict[str, Any] = raw_logsource if isinstance(raw_logsource, dict) else {}
    detection: dict[str, Any] = raw_detection if isinstance(raw_detection, dict) else {}
    return {
        "title": doc.get("title"),
        "id": doc.get("id"),
        "status": doc.get("status"),
        "description": doc.get("description"),
        "author": doc.get("author"),
        "date": doc.get("date"),
        "logsource": {
            "product": logsource.get("product"),
            "category": logsource.get("category"),
            "service": logsource.get("service"),
        },
        "detection": detection,
        "condition": detection.get("condition"),
        "fields": doc.get("fields") or [],
        "falsepositives": doc.get("falsepositives") or [],
        "level": doc.get("level"),
        "tags": doc.get("tags") or [],
    }


_SYSLOG_PRI_RE = re.compile(r"^<(\d+)>([A-Z][a-z]{2}\s+\d+\s[\d:]+)\s+(\S+)\s+")
_SYSLOG_ISO_RE = re.compile(r"^(\d{4}-\d\d-\d\dT[\d:.]+(?:Z|[+-]\d\d:?\d\d)?)\s+(\S+)\s+")
_CEF_EXT_KEY_RE = re.compile(r"([A-Za-z][A-Za-z0-9_.\[\]-]*)=")


@register(
    "cef",
    "jsonl",
    label="CEF / syslog log -> JSONL",
    notes="One object per line; a non-CEF line is kept as {_raw, _parse_error}.",
)
def cef_to_jsonl(in_path: Path, out_path: Path, opts: dict[str, Any]) -> tuple[int, list[str]]:
    """Parse each CEF (optionally syslog-prefixed) line into a JSON object, one per output line."""
    warnings: list[str] = []
    try:
        lines = in_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return 0, [f"{in_path.name}: could not read: {exc}"]
    records: list[dict[str, Any]] = []
    for lineno, line in enumerate(lines, start=1):
        stripped = line.rstrip()
        if not stripped:
            continue
        record, warning = _parse_cef_line(stripped)
        if warning:
            warnings.append(f"{in_path.name}: line {lineno}: {warning}")
        records.append(record)
    with out_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(records), warnings


def _split_syslog_prefix(line: str) -> tuple[dict[str, Any] | None, str]:
    """Peel an optional syslog PRI or ISO-timestamp prefix off a log line."""
    match = _SYSLOG_PRI_RE.match(line)
    if match:
        prefix = {"pri": int(match.group(1)), "timestamp": match.group(2), "host": match.group(3)}
        return prefix, line[match.end() :]
    match = _SYSLOG_ISO_RE.match(line)
    if match:
        return {"timestamp": match.group(1), "host": match.group(2)}, line[match.end() :]
    return None, line


def _parse_cef_line(line: str) -> tuple[dict[str, Any], str | None]:
    """Return (record, warning-or-None) for one raw log line."""
    syslog, rest = _split_syslog_prefix(line)
    marker = rest.find("CEF:")
    if marker == -1:
        return {"_raw": line, "_parse_error": "no CEF: header found"}, "not a CEF line"
    parts = _split_unescaped(rest[marker:], "|", 8)
    if len(parts) < 8:
        return (
            {"_raw": line, "_parse_error": f"expected 8 CEF fields, got {len(parts)}"},
            "malformed CEF header",
        )
    header = parts[:7]
    return {
        "cef_version": header[0].split("CEF:", 1)[1],
        "device_vendor": _unescape(header[1]),
        "device_product": _unescape(header[2]),
        "device_version": _unescape(header[3]),
        "signature_id": _unescape(header[4]),
        "name": _unescape(header[5]),
        "severity": _unescape(header[6]),
        "extensions": _parse_cef_extensions(parts[7]),
        "_syslog": syslog,
    }, None


def _split_unescaped(text: str, separator: str, limit: int) -> list[str]:
    """Split on unescaped separators, yielding at most `limit` parts."""
    parts: list[str] = []
    buffer: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            buffer.append(text[index : index + 2])
            index += 2
            continue
        if char == separator and len(parts) < limit - 1:
            parts.append("".join(buffer))
            buffer = []
            index += 1
            continue
        buffer.append(char)
        index += 1
    parts.append("".join(buffer))
    return parts


def _parse_cef_extensions(text: str) -> dict[str, str]:
    """Parse the CEF extension section (key=value key=value) with escaped = and | support."""
    body = text.strip()
    keys = list(_CEF_EXT_KEY_RE.finditer(body))
    result: dict[str, str] = {}
    for position, match in enumerate(keys):
        start = match.end()
        end = keys[position + 1].start() if position + 1 < len(keys) else len(body)
        raw = body[start:end]
        if position + 1 < len(keys) and raw.endswith(" "):
            raw = raw[:-1]
        result[match.group(1)] = _unescape(raw)
    return result


def _unescape(text: str) -> str:
    """Undo CEF backslash escaping for pipe, equals, and newline."""
    return text.replace("\\|", "|").replace("\\=", "=").replace("\\n", "\n")
