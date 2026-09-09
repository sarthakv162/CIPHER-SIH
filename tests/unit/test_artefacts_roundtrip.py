"""Every artefact model round-trips its hand-written JSON fixture."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rupantar.core.artefacts import ARTEFACT_MODELS, ArtefactBase


@pytest.mark.parametrize("name", sorted(ARTEFACT_MODELS))
def test_fixture_round_trips(artefacts_dir: Path, name: str) -> None:
    """parse -> model_dump(mode=json) -> equal to the fixture, and re-parse is stable."""
    model_cls = ARTEFACT_MODELS[name]
    raw = json.loads((artefacts_dir / f"{name}.json").read_text(encoding="utf-8"))

    parsed: ArtefactBase = model_cls.model_validate(raw)
    dumped = parsed.model_dump(mode="json", by_alias=True)

    assert dumped == raw
    assert model_cls.model_validate(dumped) == parsed


# The stub runtime serves `<RUPANTAR_STUB_COMPLETION>/<json_schema name>.json`, and one
# env var names one directory — so the verification-call fixtures have to sit beside the
# artefact ones. They are named here rather than globbed, so a genuine stray still fails.
_VERIFY_FIXTURES = {"claim_extraction", "grounding_report"}


def test_every_model_has_a_fixture(artefacts_dir: Path) -> None:
    """The fixture directory holds exactly the seven artefact examples, plus the stub's
    two verification responses and nothing else."""
    present = {p.stem for p in artefacts_dir.glob("*.json")}
    assert present - _VERIFY_FIXTURES == set(ARTEFACT_MODELS)
    assert _VERIFY_FIXTURES <= present
