"""Compile a Pydantic model's JSON Schema into a GBNF grammar for llama.cpp."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel

_PRIMITIVE_RULES: list[tuple[str, str]] = [
    ("ws", r"[ \t\n]*"),
    (
        "string",
        r'"\"" ( [^"\\\x00-\x1F] | "\\" ( ["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] '
        r'[0-9a-fA-F] [0-9a-fA-F] ) )* "\""',
    ),
    ("integer", r'"-"? ( "0" | [1-9] [0-9]* )'),
    ("number", r'"-"? ( "0" | [1-9] [0-9]* ) ( "." [0-9]+ )? ( [eE] [-+]? [0-9]+ )?'),
    ("boolean", r'"true" | "false"'),
    ("value", r'string | integer | number | boolean | "null"'),
]
_PRIMITIVE_TYPES = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
}


def gbnf_for(model: type[BaseModel]) -> str:
    """Return a GBNF grammar string that accepts exactly this model's JSON serialisation."""
    schema = model.model_json_schema()
    builder = _Builder(schema.get("$defs", {}))
    builder.visit(schema, "root")
    return _render(builder.rules)


class _Builder:
    """Walks a JSON Schema, emitting named GBNF rules and resolving local `$ref`s."""

    def __init__(self, defs: dict[str, Any]) -> None:
        """Bind the `$defs` block used to resolve references."""
        self._defs = defs
        self.rules: dict[str, str] = {}
        self._building: set[str] = set()

    def visit(self, node: dict[str, Any], name: str) -> str:
        """Emit rules for `node` and return the GBNF expression that matches it."""
        if "$ref" in node:
            return self._ref_rule(str(node["$ref"]))
        if "enum" in node:
            return self._literal_rule(name, list(node["enum"]))
        if "const" in node:
            return self._literal_rule(name, [node["const"]])
        kind = node.get("type")
        if kind == "object":
            return self._object_rule(name, node)
        if kind == "array":
            return self._array_rule(name, node)
        if isinstance(kind, str) and kind in _PRIMITIVE_TYPES:
            return _PRIMITIVE_TYPES[kind]
        if "anyOf" in node:
            return self._any_of_rule(name, list(node["anyOf"]))
        return "value"

    def _ref_rule(self, ref: str) -> str:
        """Resolve `#/$defs/Name` to a shared, memoised rule name."""
        key = ref.split("/")[-1]
        rule_name = _sanitize(key)
        if rule_name not in self.rules and rule_name not in self._building:
            self._building.add(rule_name)
            expr = self.visit(self._defs[key], rule_name)
            self._building.discard(rule_name)
            self.rules.setdefault(rule_name, expr)
        return rule_name

    def _object_rule(self, name: str, node: dict[str, Any]) -> str:
        """Emit an object rule with every property, in schema order, all required."""
        props: dict[str, Any] = node.get("properties", {})
        tokens: list[str] = ['"{"', "ws"]
        for index, (key, sub_schema) in enumerate(props.items()):
            if index:
                tokens += ['","', "ws"]
            sub = self.visit(sub_schema, f"{name}-{_sanitize(key)}")
            tokens += [_gbnf_literal(json.dumps(key)), "ws", '":"', "ws", sub, "ws"]
        tokens.append('"}"')
        self.rules[name] = " ".join(tokens)
        return name

    def _array_rule(self, name: str, node: dict[str, Any]) -> str:
        """Emit an array rule honouring `minItems` / `maxItems` when present."""
        item = self.visit(node.get("items", {"type": "string"}), f"{name}-item")
        body = _repetition(item, node.get("minItems"), node.get("maxItems"))
        self.rules[name] = f'"[" ws {body} "]"'
        return name

    def _literal_rule(self, name: str, values: list[Any]) -> str:
        """Emit an alternation of exact double-quoted JSON string literals."""
        alts = " | ".join(_gbnf_literal(json.dumps(value)) for value in values)
        self.rules[name] = f"( {alts} )"
        return name

    def _any_of_rule(self, name: str, options: list[dict[str, Any]]) -> str:
        """Emit an alternation over an `anyOf`, mapping `{"type": "null"}` to `"null"`."""
        alts: list[str] = []
        for index, option in enumerate(options):
            if option.get("type") == "null":
                alts.append('"null"')
            else:
                alts.append(self.visit(option, f"{name}-{index}"))
        self.rules[name] = "( " + " | ".join(alts) + " )"
        return name


def _repetition(item: str, low: int | None, high: int | None) -> str:
    """GBNF for a JSON array body of `item` with the given item-count bounds."""
    lo = low or 0
    one = f"{item} ws"
    more = f'( "," ws {item} ws )'
    if high is None:
        return f"{one} {more}{{{lo - 1},}}" if lo >= 1 else f"( {one} {more}* )?"
    high_more = high - 1
    if high_more < 0:
        return ""
    core = f"{one} {more}{{{max(lo - 1, 0)},{high_more}}}"
    return core if lo >= 1 else f"( {core} )?"


def _sanitize(text: str) -> str:
    """Turn an arbitrary schema name into a safe GBNF rule identifier."""
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "-", text).strip("-").lower()
    return cleaned or "x"


def _gbnf_literal(text: str) -> str:
    """Wrap `text` as a GBNF double-quoted literal, escaping the special characters."""
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _render(rules: dict[str, str]) -> str:
    """Render `root` first, then the remaining rules, then the shared primitives."""
    ordered = ["root", *[name for name in rules if name != "root"]]
    lines = [f"{name} ::= {rules[name]}" for name in ordered if name in rules]
    lines += [f"{name} ::= {body}" for name, body in _PRIMITIVE_RULES]
    return "\n".join(lines) + "\n"
