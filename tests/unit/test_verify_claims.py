"""verify.claims.extract_claims: one brain call across every artefact, parsed and validated."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rupantar.core.artefacts import ExecutiveSummary
from rupantar.core.errors import VerificationError
from rupantar.verify.claims import extract_claims

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "artefacts" / "executive_summary.json"


class _FakeClient:
    """Returns one canned completion and records every call made to it."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.calls = 0
        self.last_messages: list[dict[str, str]] | None = None

    async def complete(self, messages: list[dict[str, str]], **_kw: Any) -> str:
        self.calls += 1
        self.last_messages = messages
        return self._response


def _summary() -> ExecutiveSummary:
    return ExecutiveSummary.model_validate_json(_FIXTURE.read_text(encoding="utf-8"))


async def test_extract_claims_returns_parsed_list_from_one_call() -> None:
    payload = {
        "claims": [
            {
                "id": "C1",
                "claim": "4,200 endpoints were compromised",
                "artefact_type": "executive_summary",
                "cited_sources": ["E1"],
            }
        ]
    }
    client = _FakeClient(json.dumps(payload))
    claims = await extract_claims(
        [("executive_summary", _summary())], client, params={"max_tokens": 500, "temperature": 0.0}
    )
    assert client.calls == 1
    assert [c.id for c in claims] == ["C1"]
    assert claims[0].cited_sources == ["E1"]


async def test_extract_claims_covers_every_artefact_in_one_call() -> None:
    client = _FakeClient(json.dumps({"claims": []}))
    artefacts = [("executive_summary", _summary()), ("executive_summary", _summary())]
    await extract_claims(artefacts, client, params={})
    assert client.calls == 1
    assert client.last_messages is not None
    user_turn = client.last_messages[-1]["content"]
    assert user_turn.count("## artefact_type: executive_summary") == 2


async def test_invalid_json_raises_verification_error() -> None:
    client = _FakeClient("not json at all")
    with pytest.raises(VerificationError):
        await extract_claims([("executive_summary", _summary())], client, params={})
