"""Assemble a video package: storyboard JSON, panel PNGs, optional narration and mp4.

Uses the ``ffmpeg`` and ``piper`` CLIs as media tools (not model processes). Every external
tool failure is caught and recorded as a storyboard ``render_warnings`` entry; this renderer
never raises. ``PIL`` is imported inside the drawing helpers (INV-3).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rupantar.render.subtitle import render_srt

_CANVAS = (1280, 720)
_BG = (11, 31, 51)
_FG = (255, 255, 255)
_ACCENT = (224, 52, 45)
_MUTED = (159, 194, 224)
_TTS_MODEL = Path("models/tts/en_US-lessac-medium.onnx")  # matches configs/models.yaml tts.path
_NO_PIPER = "piper (or its voice model) not available — video has no narration"
_SOFT_SUBS = "subtitles muxed as a selectable track (ffmpeg build lacks the burn-in filter)"
_NO_SUBS = "subtitles not embedded (ffmpeg lacks subtitle support) — use the .srt sidecar"
_TEMP_GLOBS = ("_nar_*.wav", "_nar_list.txt", "_subs.srt")


def render_video(artefact: Any, path: Path, *, max_scene_seconds: int = 60) -> list[Path]:
    """Write storyboard, panels, and (when the tools exist) narration and mp4; return the files."""
    out_dir = path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    written: list[Path] = []
    try:
        panels = _write_panels(out_dir, artefact, warnings)
        written.extend(panels)
        narration = _write_narration(out_dir, artefact, warnings)
        if narration is not None:
            written.append(narration)
        mp4 = _write_mp4(out_dir, artefact, panels, narration, warnings, max_scene_seconds)
        if mp4 is not None:
            written.append(mp4)
    finally:
        _cleanup(out_dir)
    written.insert(0, _write_storyboard(out_dir, artefact, warnings))
    if warnings:
        warn_path = out_dir / "video_package.warnings.txt"
        warn_path.write_text("\n".join(warnings) + "\n", encoding="utf-8")
        written.append(warn_path)
    return [p for p in dict.fromkeys(written) if p.is_file()]


def _scene_timeline(scenes: list[Any]) -> list[dict[str, Any]]:
    """One dict per scene with cumulative start/end derived from duration_seconds."""
    rows: list[dict[str, Any]] = []
    start = 0
    for index, scene in enumerate(scenes, 1):
        duration = int(scene.duration_seconds)
        rows.append(
            {
                "index": index,
                "start": start,
                "end": start + duration,
                "duration_seconds": duration,
                "scene_description": scene.scene_description,
                "on_screen_text": scene.on_screen_text,
                "narration": scene.narration,
                "visual_recommendation": scene.visual_recommendation,
                "b_roll_suggestions": list(scene.b_roll_suggestions),
            }
        )
        start += duration
    return rows


def _write_storyboard(out_dir: Path, artefact: Any, warnings: list[str]) -> Path:
    """Write storyboard.json with the scene timeline and any render warnings."""
    data = {
        "logline": artefact.logline,
        "runtime_seconds_target": artefact.runtime_seconds_target,
        "subtitle_hint": artefact.subtitle_hint,
        "scenes": _scene_timeline(artefact.scenes),
        "render_warnings": warnings,
    }
    target = out_dir / "storyboard.json"
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def _wrap(text: str, width: int) -> list[str]:
    """Word-wrap `text` to `width` columns, never returning an empty list."""
    return textwrap.wrap(text.strip(), width=width) or [""]


def _font(size: int) -> Any:
    """The Pillow default bitmap font at `size` (falling back if the size arg is unsupported)."""
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _draw_panel(target: Path, index: int, scene: Any, logline: str) -> None:
    """Render one 1280x720 storyboard panel PNG for `scene`."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", _CANVAS, _BG)
    draw = ImageDraw.Draw(image)
    draw.text((60, 40), f"SCENE {index}", font=_font(30), fill=_ACCENT)
    y = 150
    for line in _wrap(scene.on_screen_text or scene.scene_description, 26):
        draw.text((60, y), line, font=_font(58), fill=_FG)
        y += 74
    y += 24
    for line in _wrap(scene.visual_recommendation, 64):
        draw.text((60, y), line, font=_font(24), fill=_MUTED)
        y += 32
    footer = _wrap(logline, 96)[:2]
    fy = _CANVAS[1] - 40 - 26 * len(footer)
    for line in footer:
        draw.text((60, fy), line, font=_font(20), fill=_MUTED)
        fy += 26
    image.save(target, format="PNG")


def _write_panels(out_dir: Path, artefact: Any, warnings: list[str]) -> list[Path]:
    """Draw one panel PNG per scene; a failed panel is skipped with a warning, not raised."""
    panels: list[Path] = []
    for index, scene in enumerate(artefact.scenes, 1):
        target = out_dir / f"panel_{index:02d}.png"
        try:
            _draw_panel(target, index, scene, artefact.logline)
        except Exception as exc:  # noqa: BLE001 - degrade, never crash the job
            warnings.append(f"panel {index} not rendered ({type(exc).__name__}: {exc})")
            continue
        panels.append(target)
    return panels


def _write_narration(out_dir: Path, artefact: Any, warnings: list[str]) -> Path | None:
    """Synthesise per-scene narration with piper and concat to narration.wav, or warn and skip."""
    if shutil.which("piper") is None or not _TTS_MODEL.is_file():
        warnings.append(_NO_PIPER)
        return None
    scene_wavs: list[Path] = []
    try:
        for index, scene in enumerate(artefact.scenes, 1):
            wav = out_dir / f"_nar_{index:02d}.wav"
            subprocess.run(
                ["piper", "--model", str(_TTS_MODEL.resolve()), "--output_file", wav.name],
                input=scene.narration.encode("utf-8"),
                cwd=out_dir,
                capture_output=True,
                check=True,
            )
            scene_wavs.append(wav)
        listing = out_dir / "_nar_list.txt"
        listing.write_text("".join(f"file '{w.name}'\n" for w in scene_wavs), encoding="utf-8")
        target = out_dir / "narration.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                listing.name,
                "-c",
                "copy",
                target.name,
            ],
            cwd=out_dir,
            capture_output=True,
            check=True,
        )
    except Exception as exc:  # noqa: BLE001 - degrade, never crash the job
        warnings.append(f"piper/ffmpeg narration failed ({type(exc).__name__}) — {_NO_PIPER}")
        return None
    return target if target.is_file() else None


def _write_mp4(
    out_dir: Path,
    artefact: Any,
    panels: list[Path],
    narration: Path | None,
    warnings: list[str],
    max_scene_seconds: int,
) -> Path | None:
    """Concat panels (one per scene duration) with subtitles and optional narration audio."""
    if shutil.which("ffmpeg") is None:
        warnings.append("ffmpeg not available — no video_package.mp4")
        return None
    if len(panels) != len(artefact.scenes):
        warnings.append("storyboard panels incomplete — no video_package.mp4")
        return None
    render_srt(artefact, out_dir / "_subs.srt")
    panel_inputs: list[str] = []
    for panel, scene in zip(panels, artefact.scenes, strict=True):
        seconds = max(1, min(int(scene.duration_seconds), max_scene_seconds))
        panel_inputs += ["-loop", "1", "-t", str(seconds), "-i", panel.name]
    plan = _VideoPlan(out_dir, panel_inputs, narration, len(panels), out_dir / "video_package.mp4")
    for mode, note in (("burn", ""), ("soft", _SOFT_SUBS), ("plain", _NO_SUBS)):
        if plan.build(mode):
            if note:
                warnings.append(note)
            return plan.target
    warnings.append("ffmpeg video assembly failed — no video_package.mp4")
    return None


@dataclass(frozen=True)
class _VideoPlan:
    """Panel inputs plus optional narration; renders the concat mp4 in a chosen subtitle mode."""

    out_dir: Path
    panel_inputs: list[str]
    narration: Path | None
    count: int
    target: Path

    def command(self, mode: str) -> list[str]:
        """Build the ffmpeg argv for one subtitle mode (`burn`, `soft`, or `plain`)."""
        cmd = ["ffmpeg", "-y", *self.panel_inputs]
        if self.narration is not None:
            cmd += ["-i", self.narration.name]
        if mode == "soft":
            cmd += ["-i", "_subs.srt"]
        chain = "".join(f"[{i}:v]" for i in range(self.count))
        if mode == "burn":
            fg = (
                f"{chain}concat=n={self.count}:v=1:a=0[v];"
                "[v]subtitles=_subs.srt:force_style='Fontsize=18'[vs]"
            )
        else:
            fg = f"{chain}concat=n={self.count}:v=1:a=0[vs]"
        cmd += ["-filter_complex", fg, "-map", "[vs]"]
        if self.narration is not None:
            cmd += ["-map", f"{self.count}:a", "-shortest"]
        if mode == "soft":
            subs_index = self.count + (1 if self.narration is not None else 0)
            cmd += ["-map", f"{subs_index}:s", "-c:s", "mov_text"]
        return [*cmd, "-r", "24", "-pix_fmt", "yuv420p", "-preset", "ultrafast", self.target.name]

    def build(self, mode: str) -> bool:
        """Run one ffmpeg attempt; return True when it produces the target file."""
        try:
            subprocess.run(self.command(mode), cwd=self.out_dir, capture_output=True, check=True)
        except Exception:  # noqa: BLE001 - degrade, never crash the job
            return False
        return self.target.is_file()


def _cleanup(out_dir: Path) -> None:
    """Remove intermediate wav/list/srt scratch files left by the ffmpeg and piper steps."""
    for pattern in _TEMP_GLOBS:
        for stale in out_dir.glob(pattern):
            stale.unlink(missing_ok=True)
