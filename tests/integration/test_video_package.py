"""Phase 7 verify: video_package renders storyboard + panels + mp4, degrades without piper."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from rupantar.core.artefacts import VideoPackage
from rupantar.render.base import FORMATS, render
from rupantar.render.video_render import render_video

_HAS_FFMPEG = shutil.which("ffmpeg") is not None
_HAS_PIPER = shutil.which("piper") is not None


def _load(artefacts_dir: Path) -> VideoPackage:
    return VideoPackage.model_validate_json((artefacts_dir / "video_package.json").read_text())


def _hostile() -> VideoPackage:
    scene = {
        "duration_seconds": 99999,
        "scene_description": "corridor",
        "on_screen_text": "odd ￿ ½ é ✓ chars",
        "narration": "weird \\ %s ' \" ; | chars and a very " + "long " * 80 + "tail",
        "visual_recommendation": "v",
        "b_roll_suggestions": [],
    }
    return VideoPackage(
        title="Hostile",
        runtime_seconds_target=90,
        logline="l" * 400,
        scenes=[scene, scene, scene, scene],
        full_narration="n",
        subtitle_hint="s",
    )


def test_always_produces_script_srt_storyboard(artefacts_dir: Path, tmp_path: Path) -> None:
    artefact = _load(artefacts_dir)
    render(artefact, tmp_path, formats=FORMATS["video_package"])
    for name in ("video_package.md", "video_package.srt", "storyboard.json"):
        target = tmp_path / name
        assert target.is_file() and target.stat().st_size > 0
    board = json.loads((tmp_path / "storyboard.json").read_text())
    assert len(board["scenes"]) == len(artefact.scenes)
    start = 0
    for scene, row in zip(artefact.scenes, board["scenes"], strict=True):
        assert row["start"] == start
        assert row["end"] == start + scene.duration_seconds
        start = row["end"]


def test_panels_one_per_scene_1280x720(artefacts_dir: Path, tmp_path: Path) -> None:
    from PIL import Image

    artefact = _load(artefacts_dir)
    render_video(artefact, tmp_path / "video_package.video")
    panels = sorted(tmp_path.glob("panel_*.png"))
    assert len(panels) == len(artefact.scenes)
    for panel in panels:
        assert panel.read_bytes().startswith(b"\x89PNG")
        with Image.open(panel) as image:
            assert image.size == (1280, 720)


@pytest.mark.skipif(not _HAS_FFMPEG, reason="needs ffmpeg on PATH")
def test_mp4_built_with_expected_duration(artefacts_dir: Path, tmp_path: Path) -> None:
    artefact = _load(artefacts_dir)
    paths = render_video(artefact, tmp_path / "video_package.video")
    mp4 = tmp_path / "video_package.mp4"
    assert mp4.is_file() and mp4 in paths
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(mp4),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    info = json.loads(probe.stdout)
    assert any(stream["codec_type"] == "video" for stream in info["streams"])
    expected = sum(scene.duration_seconds for scene in artefact.scenes)
    assert abs(float(info["format"]["duration"]) - expected) <= 2.0


@pytest.mark.skipif(_HAS_PIPER, reason="piper present on this machine")
def test_piper_absent_degrades_gracefully(artefacts_dir: Path, tmp_path: Path) -> None:
    artefact = _load(artefacts_dir)
    paths = render_video(artefact, tmp_path / "video_package.video")
    assert not (tmp_path / "narration.wav").exists()
    board = json.loads((tmp_path / "storyboard.json").read_text())
    assert any("piper" in warning for warning in board["render_warnings"])
    warn_path = tmp_path / "video_package.warnings.txt"
    assert warn_path.is_file() and warn_path in paths


def test_returned_paths_unique_and_real(artefacts_dir: Path, tmp_path: Path) -> None:
    artefact = _load(artefacts_dir)
    paths = render_video(artefact, tmp_path / "video_package.video")
    assert len(paths) == len(set(paths))
    for path in paths:
        assert path.is_file()
        assert tmp_path in path.parents


def test_never_raises_on_hostile_input(tmp_path: Path) -> None:
    paths = render_video(_hostile(), tmp_path / "video_package.video", max_scene_seconds=1)
    assert (tmp_path / "storyboard.json").is_file()
    assert all(path.is_file() for path in paths)
    board = json.loads((tmp_path / "storyboard.json").read_text())
    assert board["scenes"][1]["start"] == 99999


def test_no_scratch_files_left_behind(artefacts_dir: Path, tmp_path: Path) -> None:
    render_video(_load(artefacts_dir), tmp_path / "video_package.video")
    leftovers = [
        p.name for p in tmp_path.iterdir() if p.name.startswith("_nar") or p.name == "_subs.srt"
    ]
    assert not leftovers
