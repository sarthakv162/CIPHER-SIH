"""ffmpeg mp4 assembly with degradable motion: per-panel Ken Burns zoompan, falling back to
fade-ins with xfade crossfades, then fade-ins with plain concat, then a bare concat. Every
attempt is wrapped; a failure (or, for zoompan, a wrong-duration result) drops to the next tier
and records a warning. This module never raises.

Phase 9a's zoompan attempt applied a single zoompan filter *after* concatenating every looped
still into one stream; zoompan's ``d`` parameter counts output frames *per input frame it
receives*, so a many-frame input silently produced a wildly wrong duration. Phase 9c retries with
zoompan applied *per panel*, one filter per ``-r 24 -t <seconds> -loop 1`` input (many real input
frames at ``d=1`` -- one zoom-incremented output frame per input frame -- rather than one static
frame at a large ``d``), each producing its own correctly-timed clip before plain concat combines
them. Verified: a 2-panel (3s + 4s) test produced exactly 7.000s. This tier is tried first; a
result whose probed duration drifts from the planned total is treated as a failure of this tier,
not a warning-worthy success, and falls through to the fade+xfade tier exactly as before.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rupantar.render.subtitle import _timestamp

_XFADE = 0.4
_ZOOMPAN = "zoompan=z='min(zoom+0.0015,1.05)':d=1:s=1280x720:fps=24,setsar=1"
_DURATION_TOLERANCE = 2.0
_SOFT_SUBS = "subtitles muxed as a selectable track (ffmpeg build lacks the burn-in filter)"
_NO_SUBS = "subtitles not embedded (ffmpeg lacks subtitle support) - use the .srt sidecar"
_DEGRADED = "video motion degraded to {tier} (richer ffmpeg filtergraph was rejected)"
_KENBURNS_REJECTED = "Ken Burns motion produced a wrong-duration clip - fell back to fade+xfade"

# (motion label, use crossfades, use per-panel Ken Burns zoompan)
_MOTION_TIERS: tuple[tuple[str, bool, bool], ...] = (
    ("zoompan", False, True),
    ("fade+xfade", True, False),
    ("fade", False, False),
    ("concat", False, False),
)


def _has_burn_in() -> bool:
    """Whether this ffmpeg build carries the libass-backed ``subtitles`` filter."""
    try:
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, check=True
        )
    except Exception:  # noqa: BLE001 - no ffmpeg / probe failed -> assume no burn-in
        return False
    return " subtitles " in out.stdout


def write_subs(out_dir: Path, plans: list, target_name: str = "_subs.srt") -> Path:
    """Write an SRT timed to the panel plan (one cue per narrated panel)."""
    lines: list[str] = []
    start = 0.0
    cue = 0
    for plan in plans:
        end = start + plan.duration
        if plan.narration.strip():
            cue += 1
            lines += [
                str(cue),
                f"{_timestamp(start)} --> {_timestamp(end)}",
                plan.narration.strip(),
                "",
            ]
        start = end
    path = out_dir / target_name
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def build_mp4(
    out_dir: Path,
    plans: list,
    panels: list[Path],
    narration: Path | None,
    warnings: list[str],
) -> Path | None:
    """Assemble video_package.mp4 from the panel plan, degrading motion then subtitles."""
    if shutil.which("ffmpeg") is None:
        warnings.append("ffmpeg not available - no video_package.mp4")
        return None
    if len(panels) != len(plans) or not panels:
        warnings.append("storyboard panels incomplete - no video_package.mp4")
        return None
    write_subs(out_dir, plans)
    durations = [max(1, int(plan.duration)) for plan in plans]
    inputs: list[str] = []
    for panel, seconds in zip(panels, durations, strict=True):
        inputs += ["-r", "24", "-loop", "1", "-t", str(seconds), "-i", panel.name]
    plan = _VideoPlan(
        out_dir, inputs, durations, narration, len(panels), out_dir / "video_package.mp4"
    )
    subs_tiers = (["burn"] if _has_burn_in() else []) + ["soft", "plain"]
    kenburns_rejected = False
    for tier_index, (motion, xfade, kenburns) in enumerate(_MOTION_TIERS):
        for subs in subs_tiers:
            if plan.build(motion, xfade, subs, kenburns):
                _note(warnings, tier_index, motion, subs)
                if kenburns_rejected:
                    warnings.append(_KENBURNS_REJECTED)
                return plan.target
        if kenburns:
            kenburns_rejected = True
    warnings.append("ffmpeg video assembly failed - no video_package.mp4")
    return None


def _note(warnings: list[str], tier_index: int, motion: str, subs: str) -> None:
    """Record which degradation tier actually produced the file.

    Tier 0 (zoompan) is the enhancement; tier 1 (fade+xfade) is the normal, non-degraded
    outcome when Ken Burns is unavailable -- only tier 2+ is an actual degradation.
    """
    if tier_index >= 2:
        warnings.append(_DEGRADED.format(tier=motion))
    if subs == "soft":
        warnings.append(_SOFT_SUBS)
    elif subs == "plain":
        warnings.append(_NO_SUBS)


@dataclass(frozen=True)
class _VideoPlan:
    """Panel inputs plus optional narration; renders the mp4 in a chosen motion/subs mode."""

    out_dir: Path
    inputs: list[str]
    durations: list[int]
    narration: Path | None
    count: int
    target: Path

    def _stream(self, index: int, motion: str) -> str:
        """The per-panel filter chain producing label ``[v<index>]``."""
        base = "fps=24,scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,setsar=1"
        body = base if motion == "concat" else f"{base},fade=t=in:st=0:d=0.5"
        return f"[{index}:v]{body}[v{index}];"

    def _kenburns_combine(self) -> tuple[str, str]:
        """Per-panel Ken Burns zoompan streams, plainly concatenated (no crossfade)."""
        streams = "".join(f"[{i}:v]{_ZOOMPAN}[v{i}];" for i in range(self.count))
        labels = "".join(f"[v{i}]" for i in range(self.count))
        return f"{streams}{labels}concat=n={self.count}:v=1:a=0[vc]", "vc"

    def _combine(self, motion: str, xfade: bool, kenburns: bool = False) -> tuple[str, str]:
        """Filtergraph that merges the panel streams; returns (graph, final label)."""
        if kenburns:
            return self._kenburns_combine()
        streams = "".join(self._stream(i, motion) for i in range(self.count))
        if not xfade or self.count < 2:
            labels = "".join(f"[v{i}]" for i in range(self.count))
            return f"{streams}{labels}concat=n={self.count}:v=1:a=0[vc]", "vc"
        parts: list[str] = [streams.rstrip(";")]
        prev, cum = "v0", self.durations[0]
        for k in range(1, self.count):
            offset = cum - k * _XFADE
            if offset <= 0:
                raise ValueError("scene too short for a crossfade")
            parts.append(
                f"[{prev}][v{k}]xfade=transition=fade:duration={_XFADE}:offset={offset:.3f}[x{k}]"
            )
            prev, cum = f"x{k}", cum + self.durations[k]
        return ";".join(parts), prev

    def command(self, motion: str, xfade: bool, subs: str, kenburns: bool = False) -> list[str]:
        """Build the ffmpeg argv for one (motion, subs, kenburns) combination."""
        cmd = ["ffmpeg", "-y", *self.inputs]
        if self.narration is not None:
            cmd += ["-i", self.narration.name]
        if subs == "soft":
            cmd += ["-i", "_subs.srt"]
        graph, final = self._combine(motion, xfade, kenburns)
        if subs == "burn":
            graph += f";[{final}]subtitles=_subs.srt:force_style='Fontsize=18'[vs]"
        else:
            graph += f";[{final}]null[vs]"
        cmd += ["-filter_complex", graph, "-map", "[vs]"]
        if self.narration is not None:
            cmd += ["-map", f"{self.count}:a"]
        if subs == "soft":
            subs_index = self.count + (1 if self.narration is not None else 0)
            cmd += ["-map", f"{subs_index}:s", "-c:s", "mov_text"]
        return [*cmd, "-r", "24", "-pix_fmt", "yuv420p", "-preset", "ultrafast", self.target.name]

    def build(self, motion: str, xfade: bool, subs: str, kenburns: bool = False) -> bool:
        """Run one ffmpeg attempt; return True when it produces a correctly-timed target file."""
        try:
            argv = self.command(motion, xfade, subs, kenburns)
        except ValueError:
            return False
        try:
            subprocess.run(argv, cwd=self.out_dir, capture_output=True, check=True)
        except Exception:  # noqa: BLE001 - degrade, never crash the job
            return False
        if not self.target.is_file():
            return False
        if kenburns and not _duration_matches(self.target, sum(self.durations)):
            return False
        return True


def _duration_matches(path: Path, expected: float) -> bool:
    """Whether ``path``'s probed duration is within tolerance of ``expected`` seconds."""
    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return abs(float(probe.stdout.strip()) - expected) <= _DURATION_TOLERANCE
    except Exception:  # noqa: BLE001 - unable to probe counts as a misbehaving result
        return False
