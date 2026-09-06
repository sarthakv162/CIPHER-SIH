"""Defensive JSON parsing for brain responses, shared by the verification calls."""

from __future__ import annotations

import json
import re
from typing import Any

from rupantar.core.errors import VerificationError

_FENCE_HEAD = re.compile(r"^```[a-zA-Z0-9]*\s*")
_FENCE_TAIL = re.compile(r"\s*```$")


def loads_json(raw: str, *, call: str) -> Any:
    """Parse `raw` as JSON, stripping a ```json fence, raising VerificationError on failure."""
    text = _FENCE_TAIL.sub("", _FENCE_HEAD.sub("", raw.strip()))
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise VerificationError(
            f"verification call {call!r} returned unparseable JSON ({exc}); "
            "the transform and its artefacts are unaffected"
        ) from exc
