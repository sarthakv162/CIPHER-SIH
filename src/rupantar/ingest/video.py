"""ffmpeg-driven video ingestion: scene-change keyframes and a mono 16 kHz audio track."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

_Run = Callable[..., "subprocess.CompletedProcess[str]"]


def _run_ffmpeg(argv: list[str], run: _Run) -> subprocess.CompletedProcess[str]:
    """Invoke ffmpeg/ffprobe capturing text output; callers inspect returncode."""
    return run(argv, capture_output=True, text=True, check=False)


def keyframes(
    video_path: Path,
    out_dir: Path,
    *,
    max_frames: int = 6,
    scene_threshold: float = 0.3,
    run: _Run = subprocess.run,
) -> tuple[list[Path], list[str]]:
    """Extract scene-change keyframes as PNGs, falling back to even sampling; (paths, warnings)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = video_path.stem
    pattern = str(out_dir / f"{stem}-kf%03d.png")
    _run_ffmpeg(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"select='gt(scene,{scene_threshold})'",
            "-fps_mode",
            "vfr",
            "-frames:v",
            str(max_frames),
            pattern,
        ],
        run,
    )
    frames = sorted(out_dir.glob(f"{stem}-kf*.png"))
    if len(frames) >= 2:
        return frames[:max_frames], []

    for stale in frames:
        stale.unlink(missing_ok=True)
    sampled, warnings = _even_sample(video_path, out_dir, max_frames, run)
    warnings.append(f"few scene changes; sampled {len(sampled)} frames across the timeline")
    return sampled, warnings


def _even_sample(
    video_path: Path, out_dir: Path, max_frames: int, run: _Run
) -> tuple[list[Path], list[str]]:
    """Grab `max_frames` frames spread evenly across the clip duration."""
    duration = _probe_duration(video_path, run)
    if duration <= 0:
        return [], [f"could not read duration of {video_path.name}; no keyframes extracted"]
    out: list[Path] = []
    for index in range(max_frames):
        timestamp = duration * (index + 0.5) / max_frames
        target = out_dir / f"{video_path.stem}-fb{index:03d}.png"
        result = _run_ffmpeg(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                str(target),
            ],
            run,
        )
        if result.returncode == 0 and target.is_file():
            out.append(target)
    return out, []


def _probe_duration(video_path: Path, run: _Run) -> float:
    """Seconds of media in `video_path` via ffprobe, or 0.0 when it cannot be read."""
    result = _run_ffmpeg(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(video_path),
        ],
        run,
    )
    try:
        return float((result.stdout or "").strip())
    except ValueError:
        return 0.0


def extract_audio(
    video_path: Path, out_path: Path, *, run: _Run = subprocess.run
) -> tuple[Path | None, list[str]]:
    """Extract a mono 16 kHz WAV track; (None, warning) when the video has no audio stream."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result = _run_ffmpeg(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(out_path),
        ],
        run,
    )
    if result.returncode != 0 or not out_path.is_file() or out_path.stat().st_size == 0:
        return None, [f"no audio track extracted from {video_path.name}"]
    return out_path, []
