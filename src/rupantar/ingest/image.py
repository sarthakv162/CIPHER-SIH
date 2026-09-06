"""VLM image captioning into an ImageInsight, with one validation retry."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from pydantic import ValidationError

from rupantar.core.schemas import ImageInsight

if TYPE_CHECKING:
    from rupantar.models.client import LlamaClient

_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
_INSTRUCTION = (
    "Describe this image for an analyst dossier. Return a single JSON object with keys "
    "'caption' (one or two sentences), 'extracted_text' (all legible text verbatim, or an "
    "empty string), and 'notable_elements' (a list of short strings). JSON only."
)
_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {"name": "ImageInsight", "schema": ImageInsight.model_json_schema()},
}
_FENCE = re.compile(r"^```[a-zA-Z0-9]*\s*|\s*```$")


async def caption_image(path: Path, client: LlamaClient) -> tuple[ImageInsight | None, list[str]]:
    """Caption one image via the VLM; return (insight, warnings), never raising."""
    try:
        data_url = _data_url(path)
    except OSError as exc:
        return None, [f"could not read image {path.name}: {exc}"]

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": _INSTRUCTION},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]
    last: Exception | None = None
    for _ in range(2):
        try:
            raw = await client.complete(
                cast("list[dict[str, str]]", messages),
                response_format=_RESPONSE_FORMAT,
                max_tokens=512,
                temperature=0.0,
            )
        except Exception as exc:  # noqa: BLE001 - a model/transport failure is a warning
            return None, [f"VLM call failed for {path.name}: {type(exc).__name__}: {exc}"]
        try:
            payload = json.loads(_FENCE.sub("", raw.strip()))
            payload["source_name"] = path.name
            return ImageInsight.model_validate(payload), []
        except (ValueError, ValidationError) as exc:
            last = exc
            messages = [
                *messages,
                {"role": "assistant", "content": raw},
                {"role": "user", "content": f"That was invalid: {exc}. Return corrected JSON."},
            ]
    return None, [f"VLM output for {path.name} failed schema validation twice; last error: {last}"]


def _data_url(path: Path) -> str:
    """Base64 data URL for an image file, defaulting unknown suffixes to image/png."""
    mime = _MIME.get(path.suffix.lower(), "image/png")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"
