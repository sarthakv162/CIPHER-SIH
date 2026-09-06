"""Pydantic schema -> GBNF: structural properties of the generated grammar."""

from __future__ import annotations

from pydantic import BaseModel, Field

from rupantar.agents.grammar import gbnf_for
from rupantar.core.artefacts import ExecutiveSummary, Severity


def _rule(grammar: str, name: str) -> str:
    for line in grammar.splitlines():
        if line.startswith(f"{name} ::="):
            return line
    raise AssertionError(f"no rule {name!r} in grammar:\n{grammar}")


def test_executive_summary_grammar_is_structural() -> None:
    grammar = gbnf_for(ExecutiveSummary)
    assert grammar.startswith("root ::=")
    assert "string ::=" in grammar
    assert "ws ::=" in grammar
    root = _rule(grammar, "root")
    for key in ("title", "headline", "key_points", "one_line_takeaway"):
        assert f'\\"{key}\\"' in root


def test_plain_enum_field_yields_quoted_literal_alternation() -> None:
    class Model(BaseModel):
        severity: Severity

    rule = _rule(gbnf_for(Model), "severity")
    values = ("informational", "low", "medium", "high", "critical")
    expected = "severity ::= ( " + " | ".join(f'"\\"{value}\\""' for value in values) + " )"
    assert rule == expected


def test_const_field_is_pinned_to_one_literal() -> None:
    rule = _rule(gbnf_for(ExecutiveSummary), "root-artefact-type")
    assert rule == 'root-artefact-type ::= ( "\\"executive_summary\\"" )'


def test_min_and_max_items_are_reflected() -> None:
    class Model(BaseModel):
        xs: list[str] = Field(min_length=2, max_length=5)

    assert "{1,4}" in gbnf_for(Model)


def test_unbounded_array_uses_star_repetition() -> None:
    grammar = gbnf_for(ExecutiveSummary)
    assert "root-key-points ::=" in grammar
    assert "*" in _rule(grammar, "root-key-points")
