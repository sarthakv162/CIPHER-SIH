"""Brain call 1: break every generated artefact into atomic factual claims (one call, total)."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError

from rupantar.core.artefacts import ArtefactBase
from rupantar.core.errors import VerificationError
from rupantar.verify._parse import loads_json

_SYSTEM = (
    "You audit communication artefacts against their source evidence. Break each artefact into "
    "atomic factual claims: one assertion each -- a single number, a date, a named-entity "
    "relationship, or a causal statement. Split compound sentences. Do not invent claims the "
    "artefact does not make. For every claim, record the artefact_type it came from and the "
    'evidence IDs (e.g. E1, E3) that artefact listed in its "sources" field. Give each claim a '
    "short unique id (C1, C2, ...). Return only JSON matching the claim_extraction schema."
)


class _Client(Protocol):
    """The single method claim extraction needs from the leased brain client."""

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: dict[str, Any] | None,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Return one completion for `messages`."""


class Claim(BaseModel):
    """One atomic factual assertion lifted from a generated artefact."""

    id: str
    claim: str
    artefact_type: str
    cited_sources: list[str] = Field(default_factory=list)


class ClaimExtraction(BaseModel):
    """The full claim list returned by brain call 1."""

    claims: list[Claim] = Field(default_factory=list)


def _user_prompt(artefacts: list[tuple[str, ArtefactBase]]) -> str:
    """Render every artefact as labelled JSON for the extraction call."""
    parts = [
        f"## artefact_type: {artefact_type}\n{artefact.model_dump_json(by_alias=True)}"
        for artefact_type, artefact in artefacts
    ]
    return "# GENERATED ARTEFACTS\n\n" + "\n\n".join(parts)


async def extract_claims(
    artefacts: list[tuple[str, ArtefactBase]],
    client: _Client,
    *,
    params: dict[str, Any],
) -> list[Claim]:
    """One brain call: return the atomic claims of every artefact, tagged with their source IDs."""
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": _user_prompt(artefacts)},
    ]
    raw = await client.complete(
        messages,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "claim_extraction",
                "schema": ClaimExtraction.model_json_schema(),
            },
        },
        max_tokens=int(params.get("max_tokens", 2000)),
        temperature=float(params.get("temperature", 0.0)),
    )
    try:
        return ClaimExtraction.model_validate(loads_json(raw, call="claim_extraction")).claims
    except ValidationError as exc:
        raise VerificationError(
            f"claim extraction produced JSON that is not a ClaimExtraction ({exc}); "
            "artefacts are delivered regardless"
        ) from exc
