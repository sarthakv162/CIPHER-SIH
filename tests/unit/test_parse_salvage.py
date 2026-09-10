"""A verification response cut off at max_tokens must degrade to a partial report."""

from __future__ import annotations

import json

import pytest

from rupantar.core.errors import VerificationError
from rupantar.verify._parse import loads_json


def test_intact_json_is_returned_unchanged() -> None:
    payload = {"claims": [{"id": "C1", "claim": "a"}, {"id": "C2", "claim": "b"}]}
    assert loads_json(json.dumps(payload), call="claim_extraction") == payload


def test_a_json_fence_is_still_stripped() -> None:
    assert loads_json('```json\n{"claims": []}\n```', call="x") == {"claims": []}


def test_an_array_truncated_mid_string_keeps_the_complete_elements() -> None:
    """This is the real failure from the demo: `Unterminated string` mid-element."""
    raw = (
        '{"claims": ['
        '{"id": "C1", "claim": "four thousand two hundred endpoints", "artefact_type": "a"},'
        '{"id": "C2", "claim": "five regional networks", "artefact_type": "a"},'
        '{"id": "C3", "claim": "attribution is not yet est'
    )
    recovered = loads_json(raw, call="claim_extraction")
    ids = [claim["id"] for claim in recovered["claims"]]
    assert ids == ["C1", "C2"]
    assert recovered["claims"][0]["claim"].startswith("four thousand")


def test_truncation_between_elements_keeps_all_of_them() -> None:
    raw = '{"claims": [{"id": "C1", "claim": "a"}, {"id": "C2", "claim": "b"},'
    assert len(loads_json(raw, call="x")["claims"]) == 2


def test_a_second_array_is_recovered_too() -> None:
    """`grounding_report` returns groundings AND relations in one object."""
    raw = (
        '{"groundings": [{"claim_id": "C1", "status": "SUPPORTED"}], '
        '"relations": [{"kind": "CONFLICT", "claim_ids": ["C1", "C2"]}, {"kind": "AGR'
    )
    recovered = loads_json(raw, call="grounding_report")
    assert recovered["groundings"][0]["claim_id"] == "C1"
    assert [relation["kind"] for relation in recovered["relations"]] == ["CONFLICT"]


def test_nested_braces_and_escaped_quotes_do_not_confuse_the_scanner() -> None:
    raw = (
        '{"claims": [{"id": "C1", "claim": "he said \\"4,200\\"", "meta": {"page": 3}},'
        '{"id": "C2", "claim": "trunc'
    )
    recovered = loads_json(raw, call="x")
    assert len(recovered["claims"]) == 1
    assert recovered["claims"][0]["meta"] == {"page": 3}


def test_nothing_salvageable_still_raises() -> None:
    """Salvage must never invent a report out of genuine garbage."""
    for junk in ("", "not json at all", "{", '{"claims": [', "[1, 2, 3"):
        with pytest.raises(VerificationError):
            loads_json(junk, call="claim_extraction")


def test_salvage_never_fabricates_a_partial_element() -> None:
    """The cut-off element is discarded outright, never half-filled."""
    raw = '{"claims": [{"id": "C1", "claim": "complete"}, {"id": "C2", "cla'
    recovered = loads_json(raw, call="x")
    assert recovered["claims"] == [{"id": "C1", "claim": "complete"}]
