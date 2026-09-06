"""ArtefactAgent: render a dossier-first prompt, generate, JSON-parse, schema-validate."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from string import Template
from typing import Any, Protocol

from pydantic import ValidationError

from rupantar.core.artefacts import ArtefactBase
from rupantar.core.errors import AgentError
from rupantar.core.schemas import GenerationParams

# The source dossier is identical across all seven agents, so it goes first (in the system
# turn) to keep llama-server prefix caching hot; only the user turn below varies per agent.
SHARED_PREAMBLE = (
    "You are Rupantar, an offline analyst engine. Transform the SOURCE DOSSIER below into "
    "exactly one communication artefact. Use only facts present in the dossier and do not "
    "invent details. Respond with a single JSON object and nothing else."
)

_PARAM_FIELDS = ("audience", "tone", "language", "detail", "objective", "style")
_FENCE_HEAD = re.compile(r"^```[a-zA-Z0-9]*\s*")
_FENCE_TAIL = re.compile(r"\s*```$")


class _Client(Protocol):
    """The subset of LlamaClient an agent depends on."""

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: dict[str, Any] | None,
        max_tokens: int,
        temperature: float,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """Return one completion for `messages`."""

    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: dict[str, Any] | None,
        max_tokens: int,
        temperature: float,
        extra: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """Yield content deltas for `messages`."""


@dataclass
class ArtefactAgent:
    """One artefact type as a prompt template plus its schema, grammar, and validator."""

    artefact_type: str
    model_key: str
    system_prompt: str
    user_template: Template
    schema: type[ArtefactBase]
    max_tokens: int
    temperature: float
    param_hints: dict[str, dict[str, str]] = field(default_factory=dict)
    prompt_version: str = "1"
    _response_format: dict[str, Any] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Compile the schema into a reusable `response_format` (json_schema) constraint."""
        self._response_format = {
            "type": "json_schema",
            "json_schema": {"name": self.artefact_type, "schema": self.schema.model_json_schema()},
        }

    def build_messages(self, dossier_text: str, params: GenerationParams) -> list[dict[str, str]]:
        """Render the system+user messages, dossier first for prefix-cache reuse."""
        system = f"{SHARED_PREAMBLE}\n\n# SOURCE DOSSIER\n{dossier_text}"
        body = self.user_template.safe_substitute(self._hints(params))
        user = (
            f"{self.system_prompt}\n\n{body}\n\n"
            f"Return only JSON matching the {self.schema.__name__} schema."
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    async def run(
        self,
        dossier_text: str,
        params: GenerationParams,
        client: _Client,
        *,
        stream: bool = False,
    ) -> ArtefactBase:
        """Generate one artefact and return it only after `schema.model_validate` passes."""
        messages = self.build_messages(dossier_text, params)
        last: Exception | None = None
        for _ in range(2):
            raw = await self._generate(client, messages, stream)
            try:
                return self.schema.model_validate(_loads(raw))
            except (ValueError, ValidationError) as exc:
                last = exc
                messages = [
                    *messages,
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": (
                            f"Your previous response was invalid: {exc}. Return corrected JSON."
                        ),
                    },
                ]
        raise AgentError(
            f"agent {self.artefact_type!r} returned output that failed schema validation twice; "
            f"last error: {last}. Revise configs/agents/{self.artefact_type}.yaml or raise its "
            "max_tokens."
        )

    def _hints(self, params: GenerationParams) -> dict[str, str]:
        """Map each generation parameter to its configured prompt phrase."""
        out: dict[str, str] = {}
        for name in _PARAM_FIELDS:
            raw = getattr(params, name)
            value = raw.value if isinstance(raw, Enum) else str(raw)
            out[name] = self.param_hints.get(name, {}).get(value, value)
        return out

    async def _generate(
        self,
        client: _Client,
        messages: list[dict[str, str]],
        stream: bool,
    ) -> str:
        """Call the client, streaming deltas to stdout when `stream` is set."""
        if not stream:
            return await client.complete(
                messages,
                response_format=self._response_format,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
        parts: list[str] = []
        async for delta in client.stream(
            messages,
            response_format=self._response_format,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        ):
            parts.append(delta)
            print(delta, end="", flush=True)
        if parts:
            print()
        return "".join(parts)


def _loads(raw: str) -> Any:
    """Parse JSON, defensively stripping a ```json fence the grammar should have prevented."""
    text = _FENCE_TAIL.sub("", _FENCE_HEAD.sub("", raw.strip()))
    return json.loads(text)
