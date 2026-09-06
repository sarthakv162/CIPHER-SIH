"""Brain call 2 (single combined call): grounding verdicts + cross-artefact relations."""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, ValidationError, model_validator

from rupantar.core.errors import VerificationError
from rupantar.verify._parse import loads_json
from rupantar.verify.claims import Claim
from rupantar.verify.consistency import Relation

GroundingStatus = Literal["SUPPORTED", "UNSUPPORTED"]

_SYSTEM = (
    "You check extracted claims against a source evidence pack and against each other. "
    "For each claim, return a grounding verdict: SUPPORTED only if some evidence unit in the pack "
    "entails the claim (paraphrase is fine, inference beyond the evidence is not), with the "
    "evidence IDs that support it; otherwise UNSUPPORTED with an empty evidence_ids list. "
    "Then list cross-artefact relations: CONFLICT when two claims (usually different artefacts) "
    "describe the same subject with incompatible values -- state both values in detail; "
    "AGREE when >=2 artefacts state the same subject with consistent values; "
    "ORPHAN when a claim has no grounding and no counterpart in any other artefact. "
    "Do not invent a reconciling explanation for two different values on the same subject -- "
    "not a different methodology, not a different sub-scope, not an update over time -- unless "
    "the evidence pack itself states that explanation in those words. If the evidence does not "
    "explain why the numbers differ, the values are incompatible: mark it CONFLICT, not AGREE. "
    "Return only JSON matching the grounding_report schema."
)


class _Client(Protocol):
    """The single method the combined check needs from the leased brain client."""

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: dict[str, Any] | None,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Return one completion for `messages`."""


class GroundingVerdict(BaseModel):
    """Whether the evidence pack entails one claim, and which evidence units do."""

    claim_id: str
    status: GroundingStatus
    evidence_ids: list[str] = Field(default_factory=list)
    note: str = ""

    @model_validator(mode="after")
    def _unsupported_has_no_evidence(self) -> GroundingVerdict:
        """An UNSUPPORTED verdict never carries evidence IDs."""
        if self.status == "UNSUPPORTED":
            self.evidence_ids = []
        return self


class CombinedReport(BaseModel):
    """The single JSON object brain call 2 returns: grounding + consistency in one shot."""

    groundings: list[GroundingVerdict] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)


def _claims_block(claims: list[Claim]) -> str:
    """Group claims by artefact for the prompt."""
    by_type: dict[str, list[Claim]] = {}
    for claim in claims:
        by_type.setdefault(claim.artefact_type, []).append(claim)
    lines: list[str] = []
    for artefact_type, group in by_type.items():
        lines.append(f"## {artefact_type}")
        lines += [
            f"- {c.id}: {c.claim}  (artefact cited: {', '.join(c.cited_sources) or 'none'})"
            for c in group
        ]
    return "\n".join(lines)


async def combined_check(
    claims: list[Claim],
    evidence_text: str,
    client: _Client,
    *,
    params: dict[str, Any],
) -> tuple[list[GroundingVerdict], list[Relation]]:
    """One brain call: ground every claim and return every cross-artefact relation."""
    user = f"# EVIDENCE PACK\n{evidence_text}\n\n# CLAIMS\n{_claims_block(claims)}"
    raw = await client.complete(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "grounding_report",
                "schema": CombinedReport.model_json_schema(),
            },
        },
        max_tokens=int(params.get("max_tokens", 2000)),
        temperature=float(params.get("temperature", 0.0)),
    )
    try:
        report = CombinedReport.model_validate(loads_json(raw, call="grounding_report"))
    except ValidationError as exc:
        raise VerificationError(
            f"the combined grounding call produced JSON that is not a CombinedReport ({exc}); "
            "artefacts are delivered regardless"
        ) from exc
    return report.groundings, report.relations
