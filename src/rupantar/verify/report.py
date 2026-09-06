"""Assemble the two verification calls into one report. This engine does not guarantee
correctness -- it traces factual statements to source evidence and flags what it could not
substantiate."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from rupantar.core.artefacts import ArtefactBase
from rupantar.core.errors import ModelClientError, VerificationError
from rupantar.verify.claims import Claim, _Client, extract_claims
from rupantar.verify.consistency import Relation
from rupantar.verify.grounding import GroundingVerdict, combined_check

DISCLAIMER = (
    "Claims are traced to source evidence and flagged where unsubstantiated. "
    "This is not a correctness guarantee."
)

_DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "timeout_seconds": 120,
    "max_tokens": 2000,
    "temperature": 0.0,
}


class VerificationSummary(BaseModel):
    """Counts folded across every claim and relation in the transform."""

    total: int = 0
    supported: int = 0
    unsupported: int = 0
    agree: int = 0
    conflict: int = 0
    orphan: int = 0


class ClaimAssessment(BaseModel):
    """A `Claim` merged with its `GroundingVerdict`."""

    claim_id: str
    claim: str
    artefact_type: str
    status: str
    evidence_ids: list[str] = Field(default_factory=list)
    cited_sources: list[str] = Field(default_factory=list)
    note: str = ""

    @classmethod
    def merge(cls, claim: Claim, verdict: GroundingVerdict | None) -> ClaimAssessment:
        """Combine a claim with its verdict; a missing verdict counts as UNSUPPORTED."""
        if verdict is None:
            return cls(
                claim_id=claim.id,
                claim=claim.claim,
                artefact_type=claim.artefact_type,
                status="UNSUPPORTED",
                evidence_ids=[],
                cited_sources=claim.cited_sources,
                note="no grounding verdict returned for this claim",
            )
        return cls(
            claim_id=claim.id,
            claim=claim.claim,
            artefact_type=claim.artefact_type,
            status=verdict.status,
            evidence_ids=verdict.evidence_ids,
            cited_sources=claim.cited_sources,
            note=verdict.note,
        )


class VerificationReport(BaseModel):
    """Traceability report for one transform. `ok=False` only means verification did not finish."""

    transform_id: str
    generated_at: str
    disclaimer: str = DISCLAIMER
    claims: list[ClaimAssessment] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    summary: VerificationSummary = Field(default_factory=VerificationSummary)
    warnings: list[str] = Field(default_factory=list)
    ok: bool = True

    def summarise(self) -> str:
        """One-line status: '23 claims - 21 supported - 1 unsupported - 1 CONFLICT'."""
        s = self.summary
        parts = [
            f"{s.total} claims",
            f"{s.supported} supported",
            f"{s.unsupported} unsupported",
        ]
        if s.conflict:
            parts.append(f"{s.conflict} CONFLICT")
        if s.orphan:
            parts.append(f"{s.orphan} ORPHAN")
        return " · ".join(parts)

    def for_manifest(self, artefact_type: str | None = None) -> dict[str, Any]:
        """The `verification` block merged into one artefact's `.manifest.json`."""
        if not self.ok:
            return {"ok": False, "warnings": self.warnings, "disclaimer": self.disclaimer}
        block: dict[str, Any] = {
            "ok": True,
            "disclaimer": self.disclaimer,
            "summary": self.summary.model_dump(),
            "line": self.summarise(),
            "warnings": self.warnings,
        }
        if artefact_type is None:
            block["claims"] = [c.model_dump() for c in self.claims]
            block["relations"] = [r.model_dump() for r in self.relations]
            return block
        owned = {c.claim_id for c in self.claims if c.artefact_type == artefact_type}
        block["claims"] = [c.model_dump() for c in self.claims if c.artefact_type == artefact_type]
        block["relations"] = [
            r.model_dump()
            for r in self.relations
            if r.kind in ("CONFLICT", "ORPHAN") and owned.intersection(r.claim_ids)
        ]
        return block


def _summary(claims: list[ClaimAssessment], relations: list[Relation]) -> VerificationSummary:
    """Fold assessments and relations into the transform-wide counts."""
    kinds = [r.kind for r in relations]
    return VerificationSummary(
        total=len(claims),
        supported=sum(1 for c in claims if c.status == "SUPPORTED"),
        unsupported=sum(1 for c in claims if c.status != "SUPPORTED"),
        agree=kinds.count("AGREE"),
        conflict=kinds.count("CONFLICT"),
        orphan=kinds.count("ORPHAN"),
    )


def _failed(transform_id: str, generated_at: str, reason: str) -> VerificationReport:
    """A report standing in for a verification run that did not complete."""
    return VerificationReport(
        transform_id=transform_id,
        generated_at=generated_at,
        warnings=[f"verification did not complete: {reason}"],
        ok=False,
    )


async def _assemble(
    transform_id: str,
    generated_at: str,
    artefacts: list[tuple[str, ArtefactBase]],
    evidence_text: str,
    client: _Client,
    params: dict[str, Any],
) -> VerificationReport:
    """Run both brain calls and merge them into a report."""
    claims = await extract_claims(artefacts, client, params=params)
    groundings, relations = await combined_check(claims, evidence_text, client, params=params)
    by_id = {g.claim_id: g for g in groundings}
    assessments = [ClaimAssessment.merge(c, by_id.get(c.id)) for c in claims]
    return VerificationReport(
        transform_id=transform_id,
        generated_at=generated_at,
        claims=assessments,
        relations=relations,
        summary=_summary(assessments, relations),
        ok=True,
    )


async def run_verification(
    transform_id: str,
    artefacts: list[tuple[str, ArtefactBase]],
    evidence_text: str,
    client: _Client,
    *,
    params: dict[str, Any] | None,
    clock: Callable[[], datetime],
) -> VerificationReport:
    """Extract claims, ground them, and cross-check them -- two brain calls, never raising."""
    cfg = {**_DEFAULTS, **(params or {})}
    now = clock().isoformat()
    if not cfg.get("enabled", True):
        return VerificationReport(
            transform_id=transform_id,
            generated_at=now,
            ok=True,
            warnings=["verification disabled by policy"],
        )
    try:
        return await asyncio.wait_for(
            _assemble(transform_id, now, artefacts, evidence_text, client, cfg),
            timeout=float(cfg["timeout_seconds"]),
        )
    except (VerificationError, ModelClientError, TimeoutError, ValueError, OSError) as exc:
        return _failed(transform_id, now, f"{type(exc).__name__}: {exc}")
    except Exception as exc:  # noqa: BLE001 - verification must never fail a transform
        return _failed(transform_id, now, f"unexpected {type(exc).__name__}: {exc}")
