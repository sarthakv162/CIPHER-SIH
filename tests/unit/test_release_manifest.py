"""record_release: stamps an acknowledgement into a manifest without losing a field."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rupantar.audit.provenance import (
    Manifest,
    Release,
    manifest_path,
    read_manifest,
    record_release,
    write_manifest,
)
from rupantar.core.errors import ReleaseError


def _manifest() -> Manifest:
    return Manifest(
        source_sha256="abc123",
        artefact_type="advisory",
        artefact_format="json",
        model_key="brain",
        model_sha256=None,
        model_quant="stub",
        prompt_version="1",
        generation_params={"tone": "formal"},
        created_at="2026-09-09T10:00:00+00:00",
        rendered_at="2026-09-09T10:01:00+00:00",
        operator="ayush",
        app_version="0.8.0",
        job_id="job-1",
        transform_id="tr-1",
        verification={"ok": True, "line": "3 claims · 2 supported · 1 unsupported · 1 CONFLICT"},
    )


def _release() -> Release:
    return Release(
        released_by="duty-officer",
        released_at="2026-09-09T11:00:00+00:00",
        acknowledged_claim_ids=["C3", "C7"],
        acknowledged_relations=["endpoint-count"],
        note="Counts reconciled against the regional roll-up.",
    )


@pytest.fixture
def stamped(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    artefact = tmp_path / "advisory.json"
    artefact.write_text("{}", encoding="utf-8")
    target = write_manifest(artefact, _manifest())
    before = json.loads(target.read_text(encoding="utf-8"))
    return target, before


def test_release_is_recorded_into_the_manifest(stamped: tuple[Path, dict[str, object]]) -> None:
    target, _ = stamped
    record_release(target, _release())
    after = json.loads(target.read_text(encoding="utf-8"))
    assert after["release"]["released_by"] == "duty-officer"
    assert after["release"]["released_at"] == "2026-09-09T11:00:00+00:00"
    assert after["release"]["acknowledged_claim_ids"] == ["C3", "C7"]
    assert after["release"]["acknowledged_relations"] == ["endpoint-count"]
    assert after["release"]["note"].startswith("Counts reconciled")


def test_every_pre_existing_field_survives(stamped: tuple[Path, dict[str, object]]) -> None:
    target, before = stamped
    record_release(target, _release())
    after = json.loads(target.read_text(encoding="utf-8"))
    for key, value in before.items():
        if key == "release":
            continue
        assert after[key] == value
    assert set(after) == set(before) | {"release"}


def test_the_stamped_manifest_still_validates(stamped: tuple[Path, dict[str, object]]) -> None:
    target, _ = stamped
    record_release(target, _release())
    reloaded = Manifest.model_validate(read_manifest(target))
    assert reloaded.release is not None
    assert reloaded.verification == _manifest().verification


def test_a_second_release_overwrites_the_first(stamped: tuple[Path, dict[str, object]]) -> None:
    target, _ = stamped
    record_release(target, _release())
    record_release(target, _release().model_copy(update={"released_by": "watch-officer"}))
    assert read_manifest(target)["release"]["released_by"] == "watch-officer"


def test_release_creates_no_new_artefact_file(stamped: tuple[Path, dict[str, object]]) -> None:
    target, _ = stamped
    before = sorted(p.name for p in target.parent.iterdir())
    record_release(target, _release())
    assert sorted(p.name for p in target.parent.iterdir()) == before


def test_missing_manifest_raises_a_typed_error_naming_the_file(tmp_path: Path) -> None:
    missing = manifest_path(tmp_path / "advisory.json")
    with pytest.raises(ReleaseError, match="advisory.json.manifest.json"):
        record_release(missing, _release())


def test_corrupt_manifest_raises_a_typed_error(tmp_path: Path) -> None:
    broken = tmp_path / "advisory.json.manifest.json"
    broken.write_text("not json at all", encoding="utf-8")
    with pytest.raises(ReleaseError, match="not valid JSON"):
        record_release(broken, _release())
