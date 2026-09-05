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


def test_every_model_has_a_fixture(artefacts_dir: Path) -> None:
    """The fixture directory holds exactly the seven artefact examples."""
    present = {p.stem for p in artefacts_dir.glob("*.json")}
    assert present == set(ARTEFACT_MODELS)
