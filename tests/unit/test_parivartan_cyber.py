"""Phase 5: the three cyber converters (IOC CSV <-> STIX 2.1, Sigma -> JSON, CEF -> JSONL)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from rupantar.parivartan.registry import convert


@pytest.fixture
def cyber_dir(fixtures_dir: Path) -> Path:
    """Directory holding the parivartan cyber fixtures."""
    return fixtures_dir / "parivartan"


def test_ioc_csv_to_stix_bundle_shape(cyber_dir: Path, tmp_path: Path) -> None:
    """The bundle is STIX 2.1 with one indicator SDO per usable CSV row."""
    out = tmp_path / "bundle.json"
    report = convert(cyber_dir / "iocs.csv", "ioc-csv", "stix21", out, {"bundle_id": "fixed"})
    assert report.ok
    bundle = json.loads(out.read_text())
    assert bundle["type"] == "bundle" and bundle["id"] == "bundle--fixed"
    patterns = {obj["pattern"] for obj in bundle["objects"]}
    assert "[ipv4-addr:value = '198.51.100.23']" in patterns
    assert any(pattern.startswith("[file:hashes.'SHA-256' = ") for pattern in patterns)
    assert any("x-custom:value" in pattern for pattern in patterns)
    assert any("no standard STIX object path" in warning for warning in report.warnings)


def test_ioc_csv_stix_round_trip_preserves_type_value_pairs(
    cyber_dir: Path, tmp_path: Path
) -> None:
    """ioc-csv -> stix21 -> ioc-csv keeps every (type, value) pair (weird types become other)."""
    bundle = tmp_path / "bundle.json"
    back = tmp_path / "back.csv"
    assert convert(cyber_dir / "iocs.csv", "ioc-csv", "stix21", bundle).ok
    assert convert(bundle, "stix21", "ioc-csv", back).ok

    with back.open(encoding="utf-8", newline="") as handle:
        pairs = {(row["type"], row["value"]) for row in csv.DictReader(handle)}
    assert pairs == {
        ("ipv4", "198.51.100.23"),
        ("domain", "evil.example.com"),
        ("sha256", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        ("md5", "d41d8cd98f00b204e9800998ecf8427e"),
        ("url", "http://evil.example.com/a"),
        ("email", "attacker@evil.example.com"),
        ("other", "some-value"),
    }


def test_stix_to_ioc_csv_skips_non_indicators(tmp_path: Path) -> None:
    """A bundle with a non-indicator object drops it with a warning, not an error."""
    bundle = tmp_path / "b.json"
    bundle.write_text(
        json.dumps(
            {
                "type": "bundle",
                "id": "bundle--x",
                "objects": [
                    {"type": "identity", "id": "identity--1", "name": "ACME"},
                    {
                        "type": "indicator",
                        "id": "indicator--1",
                        "pattern": "[domain-name:value = 'a.example']",
                        "pattern_type": "stix",
                        "name": "n",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "o.csv"
    report = convert(bundle, "stix21", "ioc-csv", out)
    assert report.rows == 1
    assert any("non-indicator" in warning for warning in report.warnings)


def test_sigma_to_json_normalises_keys(cyber_dir: Path, tmp_path: Path) -> None:
    """A Sigma rule maps onto the fixed key set with logsource and detection intact."""
    out = tmp_path / "rule.json"
    report = convert(cyber_dir / "sigma_rule.yml", "sigma", "sigma-json", out)
    assert report.ok and report.rows == 1
    rule = json.loads(out.read_text())
    assert rule["title"] == "Suspicious PowerShell Encoded Command"
    assert rule["logsource"] == {
        "product": "windows",
        "category": "process_creation",
        "service": None,
    }
    assert rule["condition"] == "selection"
    assert "selection" in rule["detection"]
    assert rule["falsepositives"] == ["Administrative scripts"]
    assert rule["tags"] == ["attack.execution", "attack.t1059.001"]


def test_sigma_malformed_yaml_is_a_warning(tmp_path: Path) -> None:
    """Broken YAML yields rows=0 and a warning, never a traceback."""
    bad = tmp_path / "bad.yml"
    bad.write_text("title: x\n  bad: : :\n\t- nope\n", encoding="utf-8")
    report = convert(bad, "sigma", "sigma-json", tmp_path / "o.json")
    assert report.rows == 0
    assert report.warnings


def test_cef_to_jsonl(cyber_dir: Path, tmp_path: Path) -> None:
    """Each CEF line becomes one JSON object; syslog prefixes and escapes are handled."""
    out = tmp_path / "cef.jsonl"
    report = convert(cyber_dir / "cef.log", "cef", "jsonl", out)
    assert report.ok
    records = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(records) == 6

    first = records[0]
    assert first["device_vendor"] == "Security"
    assert first["cef_version"] == "0"
    assert first["extensions"]["src"] == "10.0.0.1"
    assert first["_syslog"] is None

    syslog_line = records[2]
    assert syslog_line["_syslog"]["pri"] == 134
    assert syslog_line["_syslog"]["host"] == "gateway"

    iso_line = records[3]
    assert iso_line["_syslog"]["timestamp"] == "2024-01-15T08:22:11Z"

    escaped = records[4]
    assert escaped["extensions"]["msg"] == "Detected as Trojan|Generic"
    assert escaped["extensions"]["act"] == "Trojan=Win32"

    plain = records[5]
    assert plain["_parse_error"]
    assert "_raw" in plain
    assert any("not a CEF line" in warning for warning in report.warnings)
