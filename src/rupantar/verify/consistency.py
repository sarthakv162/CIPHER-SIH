"""Cross-artefact relation model. Filled by the single combined brain call in grounding.py."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RelationKind = Literal["AGREE", "CONFLICT", "ORPHAN"]


class Relation(BaseModel):
    """One cross-artefact finding over a set of claims.

    `AGREE`: same subject, consistent values, asserted by >=2 artefacts (corroboration).
    `CONFLICT`: same subject, incompatible values across artefacts; `detail` states both.
    `ORPHAN`: a claim with no grounding and no counterpart in any other artefact.
    """

    kind: RelationKind
    claim_ids: list[str] = Field(default_factory=list)
    subject: str = ""
    detail: str = ""
