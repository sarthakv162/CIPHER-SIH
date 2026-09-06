"""INV-6: every model output is schema-validated before it can reach a renderer."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from rupantar.agents.loader import load_agent
from rupantar.core.artefacts import ExecutiveSummary
from rupantar.core.errors import AgentError
from rupantar.core.schemas import GenerationParams

_REPO = Path(__file__).resolve().parents[2]
_AGENT = _REPO / "configs" / "agents" / "executive_summary.yaml"
_FIXTURE = _REPO / "tests" / "fixtures" / "artefacts" / "executive_summary.json"


class _FakeClient:
    """Returns one canned completion for every call."""

    def __init__(self, payload: str) -> None:
        self._payload = payload

    async def complete(self, messages: object, **_kw: object) -> str:
        return self._payload

    async def stream(self, messages: object, **_kw: object) -> AsyncIterator[str]:
        yield self._payload


async def test_valid_output_is_returned_as_a_validated_model() -> None:
    """A schema-valid completion round-trips to an ExecutiveSummary instance."""
    agent = load_agent(_AGENT)
    result = await agent.run(
        "dossier", GenerationParams(), _FakeClient(_FIXTURE.read_text(encoding="utf-8"))
    )
    assert isinstance(result, ExecutiveSummary)


async def test_unvalidated_output_never_escapes_run() -> None:
    """Output that fails validation raises AgentError instead of being returned."""
    agent = load_agent(_AGENT)
    with pytest.raises(AgentError):
        await agent.run("dossier", GenerationParams(), _FakeClient('{"title": "x"}'))
