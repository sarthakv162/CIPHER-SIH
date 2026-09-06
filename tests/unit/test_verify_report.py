"""verify.report.run_verification: assembles both calls into a report; never raises."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rupantar.core.artefacts import Advisory, ExecutiveSummary
from rupantar.verify.report import run_verification

_CLOCK = lambda: datetime(2026, 1, 1, tzinfo=UTC)  # noqa: E731
_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "artefacts"


def _exec_summary() -> ExecutiveSummary:
    return ExecutiveSummary.model_validate_json(
        (_FIXTURES / "executive_summary.json").read_text(encoding="utf-8")
    )


def _advisory() -> Advisory:
    return Advisory.model_validate_json((_FIXTURES / "advisory.json").read_text(encoding="utf-8"))


_ARTEFACTS = [("executive_summary", _exec_summary()), ("advisory", _advisory())]


class _ScriptedClient:
    """Returns each configured response in turn; each `complete()` call is recorded."""

    def __init__(self, *responses: str) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def complete(self, messages: list[dict[str, str]], **_kw: Any) -> str:
        response = self._responses[self.calls]
        self.calls += 1
        return response


class _HangingClient:
    """Sleeps past any reasonable timeout on every call."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, messages: list[dict[str, str]], **_kw: Any) -> str:
        self.calls += 1
        await asyncio.sleep(10)
        return "{}"


async def test_run_verification_assembles_a_full_report() -> None:
    claims_response = json.dumps(
        {
            "claims": [
                {
                    "id": "C1",
                    "claim": "4,200 endpoints compromised",
                    "artefact_type": "executive_summary",
                    "cited_sources": ["E1"],
                },
                {
                    "id": "C2",
                    "claim": "5,000 endpoints compromised",
                    "artefact_type": "advisory",
                    "cited_sources": ["E2"],
                },
            ]
        }
    )
    grounding_response = json.dumps(
        {
            "groundings": [
                {"claim_id": "C1", "status": "SUPPORTED", "evidence_ids": ["E1"]},
                {"claim_id": "C2", "status": "SUPPORTED", "evidence_ids": ["E2"]},
            ],
            "relations": [
                {
                    "kind": "CONFLICT",
                    "claim_ids": ["C1", "C2"],
                    "subject": "endpoints compromised",
                    "detail": "4,200 vs 5,000",
                }
            ],
        }
    )
    client = _ScriptedClient(claims_response, grounding_response)
    report = await run_verification(
        "t1", _ARTEFACTS, "evidence text", client, params={}, clock=_CLOCK
    )
    assert report.ok
    assert client.calls == 2
    assert report.summary.total == 2
    assert report.summary.conflict == 1
    assert "CONFLICT" in report.summarise()
    exec_block = report.for_manifest("executive_summary")
    assert exec_block["ok"] is True
    assert {c["claim_id"] for c in exec_block["claims"]} == {"C1"}
    assert any(r["kind"] == "CONFLICT" for r in exec_block["relations"])


async def test_invalid_claim_extraction_json_yields_not_ok_report() -> None:
    client = _ScriptedClient("not json at all")
    report = await run_verification(
        "t2", _ARTEFACTS, "evidence text", client, params={}, clock=_CLOCK
    )
    assert not report.ok
    assert report.warnings
    assert client.calls == 1


async def test_grounding_timeout_yields_not_ok_report() -> None:
    client = _HangingClient()
    report = await run_verification(
        "t3",
        _ARTEFACTS,
        "evidence text",
        client,
        params={"timeout_seconds": 0.05},
        clock=_CLOCK,
    )
    assert not report.ok
    assert report.warnings


async def test_disabled_by_policy_makes_zero_brain_calls() -> None:
    client = _ScriptedClient()
    report = await run_verification(
        "t4", _ARTEFACTS, "evidence text", client, params={"enabled": False}, clock=_CLOCK
    )
    assert report.ok
    assert client.calls == 0
    assert report.summary.total == 0
    assert any("disabled" in w for w in report.warnings)
