"""Unit coverage for storyboard timing math and the piper/ffmpeg degradation branches."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rupantar.render import video_render
from rupantar.render.video_render import _scene_timeline, render_video


class _Scene:
    def __init__(self, duration: int) -> None:
        self.duration_seconds = duration
        self.scene_description = "desc"
        self.on_screen_text = "text"
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


def test_no_ffmpeg_and_no_piper_still_writes_storyboard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(video_render.shutil, "which", lambda _name: None)
    paths = render_video(_Package([4, 4, 4, 4]), tmp_path / "video_package.video")
    board = json.loads((tmp_path / "storyboard.json").read_text())
    warnings = board["render_warnings"]
    assert any("piper" in w for w in warnings)
    assert any("ffmpeg" in w for w in warnings)
    assert not (tmp_path / "video_package.mp4").exists()
    assert not (tmp_path / "narration.wav").exists()
    assert (tmp_path / "video_package.warnings.txt") in paths
    assert all(p.is_file() for p in paths)


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
