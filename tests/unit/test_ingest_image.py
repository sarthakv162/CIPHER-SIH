"""VLM captioning: valid JSON -> ImageInsight, one retry on bad JSON, warning not raise."""

from __future__ import annotations

import json
from pathlib import Path

from rupantar.core.schemas import ImageInsight
from rupantar.ingest.image import caption_image

_PNG = Path(__file__).resolve().parents[1] / "fixtures" / "media" / "sample_image.png"

_GOOD = json.dumps(
    {
        "caption": "A colourful test pattern.",
        "extracted_text": "",
        "notable_elements": ["bars", "gradient"],
    }
)


class _ScriptedClient:
    """Returns each configured response in turn; records how many calls it saw."""

    def __init__(self, *responses: str | Exception) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def complete(self, messages: object, **_kw: object) -> str:
        response = self._responses[self.calls]
        self.calls += 1
        if isinstance(response, Exception):
            raise response
        return response


async def test_valid_json_becomes_an_image_insight() -> None:
    client = _ScriptedClient(_GOOD)
    insight, warnings = await caption_image(_PNG, client)  # type: ignore[arg-type]
    assert isinstance(insight, ImageInsight)
    assert insight.source_name == "sample_image.png"
    assert insight.notable_elements == ["bars", "gradient"]
    assert warnings == []
    assert client.calls == 1


async def test_bad_then_good_retries_once() -> None:
    client = _ScriptedClient("not json", _GOOD)
    insight, warnings = await caption_image(_PNG, client)  # type: ignore[arg-type]
    assert isinstance(insight, ImageInsight)
    assert warnings == []
    assert client.calls == 2


async def test_bad_twice_returns_none_and_a_warning() -> None:
    client = _ScriptedClient("nope", "still nope")
    insight, warnings = await caption_image(_PNG, client)  # type: ignore[arg-type]
    assert insight is None
    assert warnings and "failed schema validation twice" in warnings[0]
    assert client.calls == 2


async def test_transport_failure_is_a_warning_not_a_raise() -> None:
    client = _ScriptedClient(ConnectionResetError("boom"))
    insight, warnings = await caption_image(_PNG, client)  # type: ignore[arg-type]
    assert insight is None
    assert warnings and "VLM call failed" in warnings[0]


async def test_missing_image_file_warns(tmp_path: Path) -> None:
    insight, warnings = await caption_image(tmp_path / "gone.png", _ScriptedClient(_GOOD))  # type: ignore[arg-type]
    assert insight is None
    assert warnings and "could not read image" in warnings[0]
