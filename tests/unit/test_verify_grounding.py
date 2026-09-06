"""verify.grounding.combined_check: one brain call for both grounding verdicts and relations."""

from __future__ import annotations

import json
from typing import Any

import pytest

from rupantar.core.errors import VerificationError
from rupantar.verify.claims import Claim
from rupantar.verify.grounding import combined_check

_CLAIMS = [
    Claim(id="C1", claim="4,200 endpoints compromised", artefact_type="executive_summary"),
    Claim(id="C2", claim="5,000 endpoints compromised", artefact_type="advisory"),
    Claim(id="C3", claim="Recovery will take two to four weeks", artefact_type="advisory"),
    Claim(id="C4", claim="The moon is made of cheese", artefact_type="advisory"),
]


class _FakeClient:
    """Returns one canned completion and records every call made to it."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.calls = 0

    async def complete(self, messages: list[dict[str, str]], **_kw: Any) -> str:
        self.calls += 1
        return self._response


async def test_supported_unsupported_agree_conflict_orphan_all_parse() -> None:
    payload = {
        "groundings": [
            {"claim_id": "C1", "status": "SUPPORTED", "evidence_ids": ["E1"]},
            {"claim_id": "C2", "status": "SUPPORTED", "evidence_ids": ["E2"]},
            {"claim_id": "C3", "status": "SUPPORTED", "evidence_ids": ["E2"]},
            {"claim_id": "C4", "status": "UNSUPPORTED", "evidence_ids": []},
        ],
        "relations": [
            {
                "kind": "CONFLICT",
                "claim_ids": ["C1", "C2"],
                "subject": "endpoints compromised",
                "detail": "4,200 vs 5,000",
            },
            {"kind": "ORPHAN", "claim_ids": ["C4"], "subject": "the moon"},
        ],
    }
    client = _FakeClient(json.dumps(payload))
    groundings, relations = await combined_check(_CLAIMS, "evidence text", client, params={})
    assert client.calls == 1
    by_id = {g.claim_id: g for g in groundings}
    assert by_id["C1"].status == "SUPPORTED"
    assert by_id["C4"].status == "UNSUPPORTED"
    assert by_id["C4"].evidence_ids == []
    kinds = {r.kind for r in relations}
    assert "CONFLICT" in kinds
    assert "ORPHAN" in kinds


async def test_unsupported_verdict_never_carries_evidence_ids() -> None:
    payload = {
        "groundings": [{"claim_id": "C4", "status": "UNSUPPORTED", "evidence_ids": ["E9"]}],
        "relations": [],
    }
    client = _FakeClient(json.dumps(payload))
    groundings, _relations = await combined_check(_CLAIMS, "evidence", client, params={})
    assert groundings[0].evidence_ids == []


async def test_invalid_json_raises_verification_error() -> None:
    client = _FakeClient("{not valid json")
    with pytest.raises(VerificationError):
        await combined_check(_CLAIMS, "evidence", client, params={})
