"""ffmpeg video ingestion: scene-change keyframes with timestamps and a 16 kHz audio track."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from pathlib import Path

_Run = Callable[..., "subprocess.CompletedProcess[str]"]
_PTS_TIME = re.compile(r"pts_time:([0-9]+\.?[0-9]*)")

Keyframe = tuple[Path, float]


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
) -> tuple[list[Keyframe], list[str]]:
    """Extract scene-change keyframes as (png, timestamp) pairs, falling back to even sampling."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = video_path.stem
    pattern = str(out_dir / f"{stem}-kf%03d.png")
    result = _run_ffmpeg(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "info",
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"select='gt(scene,{scene_threshold})',showinfo",
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
        times = [float(m) for m in _PTS_TIME.findall(result.stderr or "")]
        return _pair(frames[:max_frames], times), []

    for stale in frames:
        stale.unlink(missing_ok=True)
    sampled, warnings = _even_sample(video_path, out_dir, max_frames, run)
    warnings.append(f"few scene changes; sampled {len(sampled)} frames across the timeline")
    return sampled, warnings


def _pair(frames: list[Path], times: list[float]) -> list[Keyframe]:
    """Zip frames with their showinfo timestamps, defaulting to 0.0 when a time is missing."""
    return [(frame, times[i] if i < len(times) else 0.0) for i, frame in enumerate(frames)]


def _even_sample(
    video_path: Path, out_dir: Path, max_frames: int, run: _Run
) -> tuple[list[Keyframe], list[str]]:
    """Grab `max_frames` frames spread evenly across the clip duration, tagged with seek times."""
    duration = probe_duration(video_path, run=run)
    if duration <= 0:
        return [], [f"could not read duration of {video_path.name}; no keyframes extracted"]
    out: list[Keyframe] = []
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
            out.append((target, timestamp))
    return out, []


def probe_duration(video_path: Path, *, run: _Run = subprocess.run) -> float:
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
