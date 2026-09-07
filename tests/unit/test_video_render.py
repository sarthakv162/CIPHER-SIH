"""Unit coverage for storyboard timing math and the piper/ffmpeg degradation branches."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rupantar.render import video_render
from rupantar.render._video_scene import derive_scene_type, extract_frame
from rupantar.render.video_render import _scene_timeline, render_video


class _Scene:
    def __init__(self, duration: int, on_screen_text: str = "text") -> None:
        self.duration_seconds = duration
        self.scene_description = "desc"
        self.on_screen_text = on_screen_text
        self.narration = "narration"
        self.visual_recommendation = "visual"
        self.b_roll_suggestions = ["a"]


class _Package:
    def __init__(self, durations: list[int]) -> None:
        self.logline = "logline"
        self.runtime_seconds_target = sum(durations)
        self.subtitle_hint = "hint"
        self.scenes = [_Scene(d) for d in durations]


def test_scene_timeline_is_cumulative() -> None:
    rows = _scene_timeline([_Scene(10), _Scene(5), _Scene(20)])
    assert [(r["index"], r["start"], r["end"]) for r in rows] == [
        (1, 0, 10),
        (2, 10, 15),
        (3, 15, 35),
    ]


def test_no_ffmpeg_and_no_voice_model_still_writes_storyboard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(video_render.shutil, "which", lambda _name: None)
    # piper falls back to `python -m piper`, so the voice model absence is what disables narration
    monkeypatch.setattr(video_render, "_TTS_MODEL", tmp_path / "no-such-voice.onnx")
    paths = render_video(_Package([4, 4, 4, 4]), tmp_path / "video_package.video")
    board = json.loads((tmp_path / "storyboard.json").read_text())
    warnings = board["render_warnings"]
    assert any("piper" in w for w in warnings)
    assert any("ffmpeg" in w for w in warnings)
    assert not (tmp_path / "video_package.mp4").exists()
    assert not (tmp_path / "narration.wav").exists()
    assert (tmp_path / "video_package.warnings.txt") in paths
    assert all(p.is_file() for p in paths)


def test_scene_type_derivation() -> None:
    scenes = [
        _Scene(5, "Welcome"),
        _Scene(5, '"We were blindsided," the CISO said'),
        _Scene(5, "8 days to full containment"),
        _Scene(5, "A plain narrative beat"),
        _Scene(5, "Thanks for watching"),
    ]
    types = [derive_scene_type(i, len(scenes), s) for i, s in enumerate(scenes)]
    assert types == ["title_card", "quote", "stat_block", "statement", "closing"]


def test_context_none_still_renders_panels(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(video_render.shutil, "which", lambda _name: None)
    monkeypatch.setattr(video_render, "_TTS_MODEL", tmp_path / "no-voice.onnx")
    paths = render_video(_Package([4, 4, 4, 4]), tmp_path / "video_package.video", context=None)
    panels = sorted(tmp_path.glob("panel_*.png"))
    assert len(panels) == 4
    assert all(p.is_file() for p in paths)
    board = json.loads((tmp_path / "storyboard.json").read_text())
    assert [row["scene_type"] for row in board["scenes"]] == [
        "title_card",
        "statement",
        "statement",
        "closing",
    ]


def test_broll_frame_extraction_failure_degrades(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("ffmpeg cannot read that")

    monkeypatch.setattr(video_render.subprocess, "run", _boom)
    warnings: list[str] = []
    result = extract_frame(Path("/no/such/video.mp4"), 3.0, tmp_path / "f.png", warnings)
    assert result is None
    assert any("frame extraction" in w for w in warnings)


def test_ffmpeg_failure_is_caught(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(video_render.shutil, "which", lambda name: f"/usr/bin/{name}")

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("ffmpeg exploded")

    monkeypatch.setattr(video_render.subprocess, "run", _boom)
    paths = render_video(_Package([2, 2, 2, 2]), tmp_path / "video_package.video")
    board = json.loads((tmp_path / "storyboard.json").read_text())
    assert any("ffmpeg video assembly failed" in w for w in board["render_warnings"])
    assert not (tmp_path / "video_package.mp4").exists()
    assert all(p.is_file() for p in paths)
