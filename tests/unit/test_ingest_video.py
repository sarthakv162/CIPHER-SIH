"""Video ingestion against real ffmpeg: scene-change keyframes, fallback sampling, audio track."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from rupantar.ingest.video import extract_audio, keyframes

_MEDIA = Path(__file__).resolve().parents[1] / "fixtures" / "media"
_CLIP = _MEDIA / "sample_clip.mp4"

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg on PATH")


def _spy() -> tuple[list[list[str]], object]:
    calls: list[list[str]] = []

    def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.run(argv, **kwargs)  # type: ignore[call-overload]

    return calls, run


def test_keyframes_use_a_scene_select_expression(tmp_path: Path) -> None:
    calls, run = _spy()
    frames, _warnings = keyframes(_CLIP, tmp_path, max_frames=6, run=run)  # type: ignore[arg-type]

    ffmpeg_calls = [c for c in calls if c and c[0] == "ffmpeg"]
    first_vf = next(c[c.index("-vf") + 1] for c in ffmpeg_calls if "-vf" in c)
    assert "select=" in first_vf and "scene" in first_vf
    assert "fps=" not in first_vf
    assert all(p.suffix == ".png" and p.is_file() for p in frames)
    assert len(frames) <= 6


def test_high_threshold_forces_the_fallback_warning(tmp_path: Path) -> None:
    frames, warnings = keyframes(_CLIP, tmp_path, max_frames=4, scene_threshold=0.99)
    assert any("few scene changes" in w for w in warnings)
    assert len(frames) <= 4


def test_extract_audio_produces_a_wav(tmp_path: Path) -> None:
    wav, warnings = extract_audio(_CLIP, tmp_path / "track.wav")
    assert wav is not None and wav.is_file() and wav.stat().st_size > 0
    assert warnings == []
