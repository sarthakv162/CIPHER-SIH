"""Defensive JSON parsing for brain responses, shared by the verification calls."""

from __future__ import annotations

import json
import re
from typing import Any

from rupantar.core.errors import VerificationError

_FENCE_HEAD = re.compile(r"^```[a-zA-Z0-9]*\s*")
_FENCE_TAIL = re.compile(r"\s*```$")


def loads_json(raw: str, *, call: str) -> Any:
    """Parse `raw` as JSON, stripping a ```json fence, raising VerificationError on failure.

    A response cut off at `max_tokens` is the common failure here, and it is not a
    model defect: a many-artefact transform simply has more claims than the budget
    can serialise. Rather than lose the whole report, recover the elements that did
    arrive complete -- a partial verification is worth far more than none.
    """
    text = _FENCE_TAIL.sub("", _FENCE_HEAD.sub("", raw.strip()))
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        salvaged = _salvage(text)
        if salvaged is not None:
            return salvaged
        raise VerificationError(
            f"verification call {call!r} returned unparseable JSON ({exc}); "
            "the transform and its artefacts are unaffected"
        ) from exc


def _salvage(text: str) -> dict[str, Any] | None:
    """Rebuild an object whose arrays were truncated mid-flight, or None if hopeless.

    Only handles the shape these calls actually return: a top-level object whose
    values are arrays of objects. Every complete element is kept and the partial
    tail is discarded; nothing is invented.
    """
    if not text.lstrip().startswith("{"):
        return None
    recovered = {key: _complete_elements(text, key) for key in _array_keys(text)}
    recovered = {key: value for key, value in recovered.items() if value}
    return recovered or None


def _array_keys(text: str) -> list[str]:
    """Top-level keys whose value opens an array."""
    return re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"\s*:\s*\[', text)


def _complete_elements(text: str, key: str) -> list[Any]:
    """Every fully-formed object inside `key`'s array, stopping at the truncation."""
    match = re.search(rf'"{re.escape(key)}"\s*:\s*\[', text)
    if match is None:
        return []
    elements: list[Any] = []
    index = match.end()
    while index < len(text):
        start = text.find("{", index)
        if start == -1:
            break
        end = _matching_brace(text, start)
        if end is None:
            break  # the tail was cut mid-element; everything before it still stands
        try:
            elements.append(json.loads(text[start : end + 1]))
        except (json.JSONDecodeError, ValueError):
            break
        index = end + 1
        following = text[index:].lstrip()
        if not following.startswith(","):
            break
    return elements


def _matching_brace(text: str, start: int) -> int | None:
    """Index of the `}` closing the `{` at `start`, honouring strings and escapes."""
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return None
