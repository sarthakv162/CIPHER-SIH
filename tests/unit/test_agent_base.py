"""ArtefactAgent.run: validate on success, retry once, then raise AgentError."""

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


class _ScriptedClient:
    """Returns each configured response in turn."""

    def __init__(self, *responses: str) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def complete(self, messages: object, **_kw: object) -> str:
        response = self._responses[self.calls]
        self.calls += 1
        return response

    async def stream(self, messages: object, **_kw: object) -> AsyncIterator[str]:
        response = self._responses[self.calls]
        self.calls += 1
        for char in response:
            yield char


def _agent() -> object:
    return load_agent(_AGENT)


async def test_valid_json_returns_validated_artefact() -> None:
    client = _ScriptedClient(_FIXTURE.read_text(encoding="utf-8"))
    result = await _agent().run("dossier text", GenerationParams(), client)
    assert isinstance(result, ExecutiveSummary)
    assert client.calls == 1


async def test_invalid_then_valid_retries_exactly_once() -> None:
    client = _ScriptedClient("not json at all", _FIXTURE.read_text(encoding="utf-8"))
    result = await _agent().run("dossier text", GenerationParams(), client)
    assert isinstance(result, ExecutiveSummary)
    assert client.calls == 2


async def test_invalid_twice_raises_agent_error_with_reason() -> None:
    client = _ScriptedClient("nope", "still nope")
    with pytest.raises(AgentError) as excinfo:
        await _agent().run("dossier text", GenerationParams(), client)
    message = str(excinfo.value)
    assert "executive_summary" in message
    assert "validation" in message
    assert client.calls == 2


async def test_streaming_path_reassembles_and_validates() -> None:
    client = _ScriptedClient(_FIXTURE.read_text(encoding="utf-8"))
    result = await _agent().run("d", GenerationParams(), client, stream=True)
    assert isinstance(result, ExecutiveSummary)
