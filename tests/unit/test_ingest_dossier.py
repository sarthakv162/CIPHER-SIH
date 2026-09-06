"""Dossier assembly: evidence-ID order, video-event grouping, one lease per modality."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from rupantar.core.schemas import (
    ImageInsight,
    SourceInput,
    SourceKind,
    TextBlock,
    Transcript,
    TranscriptSegment,
    VideoEvent,
)
from rupantar.ingest import dossier as mod
from rupantar.ingest.dossier import _assign_evidence_ids, _build_video_events, assemble_dossier


def _seg(start: float, end: float, text: str) -> TranscriptSegment:
    return TranscriptSegment(start=start, end=end, text=text)


def test_build_video_events_groups_by_consecutive_keyframes() -> None:
    frames = [(0.0, "opening title card"), (5.0, "speaker at lectern"), (12.0, "closing slide")]
    segments = [
        _seg(0.0, 4.0, "hello everyone"),
        _seg(4.0, 9.0, "today we discuss"),
        _seg(9.0, 15.0, "in summary"),
    ]
    events = _build_video_events("talk.mp4", frames, segments, total=20.0)

    assert [(e.start, e.end) for e in events] == [(0.0, 5.0), (5.0, 12.0), (12.0, 20.0)]
    assert events[0].caption == "opening title card"
    assert events[0].transcript == "hello everyone today we discuss"
    assert events[1].transcript == "today we discuss in summary"
    assert events[2].transcript == "in summary"
    assert all(e.source_name == "talk.mp4" for e in events)


def test_build_video_events_first_span_starts_at_zero_last_runs_to_total() -> None:
    events = _build_video_events("v.mp4", [(2.0, "a")], [], total=1.0)
    assert events[0].start == 0.0 and events[0].end == 2.0

    events = _build_video_events("v.mp4", [(2.0, "a")], [], total=30.0)
    assert events[0].start == 0.0 and events[0].end == 30.0


def test_build_video_events_empty_when_no_frames() -> None:
    assert _build_video_events("v.mp4", [], [_seg(0, 1, "x")], total=5.0) == []


def test_assign_evidence_ids_order_text_image_video_then_segments() -> None:
    text_blocks = [TextBlock(source_name="a", text="x"), TextBlock(source_name="b", text="y")]
    images = [ImageInsight(source_name="i", caption="c", extracted_text="")]
    videos = [VideoEvent(source_name="v", start=0, end=1)]
    transcripts = [
        Transcript(source_name="t", text="", segments=[_seg(0, 1, "one"), _seg(1, 2, "two")])
    ]
    _assign_evidence_ids(text_blocks, images, videos, transcripts)

    assert [b.evidence_id for b in text_blocks] == ["E1", "E2"]
    assert images[0].evidence_id == "E3"
    assert videos[0].evidence_id == "E4"
    assert [s.evidence_id for s in transcripts[0].segments] == ["E5", "E6"]


class _FakeLease:
    endpoint = "http://127.0.0.1:0"


class _FakeAcquire:
    async def __aenter__(self) -> _FakeLease:
        return _FakeLease()

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _FakeManager:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def acquire(self, key: str) -> _FakeAcquire:
        self.calls.append(f"acquire:{key}")
        return _FakeAcquire()

    async def evict(self, key: str) -> None:
        self.calls.append(f"evict:{key}")


class _FakeClient:
    def __init__(self, _endpoint: str) -> None:
        pass

    async def aclose(self) -> None:
        pass


async def test_assemble_dossier_assigns_ids_and_uses_one_lease_per_modality(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "LlamaClient", _FakeClient)
    monkeypatch.setattr(
        mod, "keyframes", lambda v, d, **k: ([(d / "f0.png", 0.0), (d / "f1.png", 6.0)], [])
    )
    monkeypatch.setattr(mod, "extract_audio", lambda v, o, **k: (o, []))
    monkeypatch.setattr(mod, "probe_duration", lambda v, **k: 12.0)

    async def fake_caption(target: Path, _client: object) -> tuple[ImageInsight, list[str]]:
        insight = ImageInsight(
            source_name=target.name, caption=f"caption of {target.name}", extracted_text=""
        )
        return insight, []

    async def fake_transcribe(target: Path, _endpoint: str) -> tuple[Transcript, list[str]]:
        return Transcript(
            source_name=target.name, text="spoken words", segments=[_seg(0.0, 8.0, "spoken words")]
        ), []

    monkeypatch.setattr(mod, "caption_image", fake_caption)
    monkeypatch.setattr(mod, "transcribe", fake_transcribe)

    (tmp_path / "pic.png").write_bytes(b"x")
    (tmp_path / "clip.mp4").write_bytes(b"y")
    sources = [
        SourceInput(kind=SourceKind.text, text="an inline briefing note"),
        SourceInput(kind=SourceKind.file, path=str(tmp_path / "pic.png")),
        SourceInput(kind=SourceKind.file, path=str(tmp_path / "clip.mp4")),
    ]
    manager = _FakeManager()

    result, _warnings = await assemble_dossier(
        sources,
        manager=manager,  # type: ignore[arg-type]
        out_dir=tmp_path / "ingest",
        new_id=lambda: "d1",
        clock=lambda: datetime.now(UTC),
    )

    assert manager.calls == ["acquire:vlm", "evict:vlm", "acquire:asr", "evict:asr"]
    assert result.text_blocks[0].evidence_id == "E1"
    assert result.image_insights[0].evidence_id == "E2"
    assert [e.evidence_id for e in result.video_events] == ["E3", "E4"]
    assert result.transcripts == []
    assert result.video_events[0].caption == "caption of f0.png"
    assert result.video_events[0].transcript == "spoken words"

    prompt = result.to_prompt_text()
    assert "[E1]" in prompt and "[E3]" in prompt
    assert "0:00–0:06" in prompt
