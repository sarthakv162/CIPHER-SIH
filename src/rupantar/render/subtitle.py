"""SRT subtitles for a video package, one cue per scene from its duration. No heavy imports."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _timestamp(seconds: float) -> str:
    """Format seconds as an SRT `HH:MM:SS,mmm` timestamp."""
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def render_srt(artefact: Any, path: Path) -> None:
    """Write one SRT cue per scene, timed by each scene's `duration_seconds`."""
    lines: list[str] = []
    start = 0.0
    for index, scene in enumerate(artefact.scenes, 1):
        end = start + scene.duration_seconds
        lines += [
            str(index),
            f"{_timestamp(start)} --> {_timestamp(end)}",
            scene.narration.strip(),
            "",
        ]
        start = end
    path.write_text("\n".join(lines), encoding="utf-8")
