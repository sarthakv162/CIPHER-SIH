"""Assemble a video package: storyboard JSON, themed panel PNGs, optional narration and mp4.

Uses the ``ffmpeg`` and ``piper`` CLIs as media tools (not model processes). Every external
tool failure is caught and recorded as a storyboard ``render_warnings`` entry; this renderer
never raises. ``PIL`` is imported inside the drawing helpers (INV-3).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from rupantar.core.errors import ConfigError
from rupantar.render._video_mux import build_mp4
from rupantar.render._video_scene import (
    PanelPlan,
    derive_scene_type,
    plan_panels,
    render_plan_panel,
)
from rupantar.render.context import RenderContext
from rupantar.render.theme import Theme, load_theme

# matches configs/models.yaml tts.path / tts.config
_TTS_MODEL = Path("models/tts/en_US-lessac-medium.onnx")
_TTS_CONFIG = Path("models/tts/en_US-lessac-medium.onnx.json")
_TTS_DATA_DIR = Path("models/tts")
_NO_PIPER = "piper (or its voice model) not available — video has no narration"
_TEMP_GLOBS = ("_nar_*.wav", "_nar_list.txt", "_subs.srt", "_frame_*.png")


def render_video(
    artefact: Any,
    path: Path,
    *,
    max_scene_seconds: int = 60,
    context: RenderContext | None = None,
) -> list[Path]:
    """Write storyboard, panels, and (when the tools exist) narration and mp4; return the files."""
    out_dir = path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    written: list[Path] = []
    theme = _resolve_theme(context, warnings)
    footer = str(getattr(artefact, "title", "video_package"))
    plans: list[PanelPlan] = []
    visual_sources: list[dict[str, str]] = []
    try:
        plans, visual_sources = plan_panels(artefact, theme, context, out_dir, warnings)
        plans = [replace(p, duration=max(1, min(p.duration, max_scene_seconds))) for p in plans]
        panels = _write_panels(out_dir, plans, footer, theme, warnings)
        written.extend(panels)
        narration = _write_narration(out_dir, artefact, warnings)
        if narration is not None:
            written.append(narration)
        mp4 = build_mp4(out_dir, plans, panels, narration, warnings)
        if mp4 is not None:
            written.append(mp4)
    except Exception as exc:  # noqa: BLE001 - degrade to storyboard-only, never crash the job
        warnings.append(f"video assembly aborted ({type(exc).__name__}: {exc})")
    finally:
        _cleanup(out_dir)
    written.insert(0, _write_storyboard(out_dir, artefact, plans, visual_sources, warnings))
    if warnings:
        warn_path = out_dir / "video_package.warnings.txt"
        warn_path.write_text("\n".join(warnings) + "\n", encoding="utf-8")
        written.append(warn_path)
    return [p for p in dict.fromkeys(written) if p.is_file()]


def _resolve_theme(context: RenderContext | None, warnings: list[str]) -> Theme:
    """Load the requested theme, degrading to the default (then a stub) if it is unavailable."""
    name = context.theme_name if context is not None else "ntro-formal"
    for candidate in dict.fromkeys([name, "ntro-formal"]):
        try:
            return load_theme(candidate)
        except ConfigError as exc:
            warnings.append(f"theme {candidate!r} unavailable ({exc}) — trying the default")
    warnings.append("no theme file found — panels use a built-in fallback palette")
    return _FALLBACK_THEME


_FALLBACK_THEME = Theme.model_validate(
    {
        "name": "fallback",
        "palette": {
            "primary": "#0b1f33",
            "accent": "#e0342d",
            "background": "#0b1f33",
            "surface": "#12324f",
            "text": "#ffffff",
            "text_muted": "#9fc2e0",
            "text_inverse": "#0b1f33",
            "severity": {
                "low": "#2e7d32",
                "medium": "#f4b400",
                "high": "#ef6c00",
                "critical": "#c62828",
            },
        },
        "type_scale": {
            "display": 132,
            "title": 58,
            "heading": 34,
            "body": 24,
            "caption": 18,
            "footer": 16,
        },
        "spacing": {"unit": 8, "steps": [4, 8, 16, 24, 32, 48, 64, 96]},
        "fonts": {"regular": [], "bold": []},
        "wordmark": {"text": "Rupantar", "logo_path": ""},
    }
)


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


def _scene_types(scenes: list[Any]) -> list[str]:
    """The derived panel layout for each scene, in order (heuristic; schema has no field)."""
    count = len(scenes)
    return [derive_scene_type(index, count, scene) for index, scene in enumerate(scenes)]


def _panel_rows(plans: list[PanelPlan]) -> list[dict[str, Any]]:
    """One dict per rendered panel: layout, duration, and any cited background evidence."""
    rows: list[dict[str, Any]] = []
    for plan in plans:
        rows.append(
            {
                "index": plan.index,
                "scene_type": plan.layout,
                "duration_seconds": plan.duration,
                "is_extra": plan.is_extra,
                "background_evidence": plan.background_evidence or None,
            }
        )
    return rows


def _write_storyboard(
    out_dir: Path,
    artefact: Any,
    plans: list[PanelPlan],
    visual_sources: list[dict[str, str]],
    warnings: list[str],
) -> Path:
    """Write storyboard.json with the scene timeline, panel plan, and any render warnings."""
    scenes = _scene_timeline(artefact.scenes)
    for row, scene_type in zip(scenes, _scene_types(artefact.scenes), strict=True):
        row["scene_type"] = scene_type
    data = {
        "logline": artefact.logline,
        "runtime_seconds_target": artefact.runtime_seconds_target,
        "subtitle_hint": artefact.subtitle_hint,
        "scenes": scenes,
        "panels": _panel_rows(plans),
        "visual_sources": visual_sources,
        "render_warnings": warnings,
    }
    target = out_dir / "storyboard.json"
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def _write_panels(
    out_dir: Path, plans: list[PanelPlan], footer: str, theme: Theme, warnings: list[str]
) -> list[Path]:
    """Draw one panel PNG per plan; a failed panel is skipped with a warning, not raised."""
    panels: list[Path] = []
    for plan in plans:
        target = out_dir / f"panel_{plan.index:02d}.png"
        try:
            render_plan_panel(target, plan, len(plans), footer, theme)
        except Exception as exc:  # noqa: BLE001 - degrade, never crash the job
            warnings.append(f"panel {plan.index} not rendered ({type(exc).__name__}: {exc})")
            continue
        panels.append(target)
    return panels


def _piper_base() -> list[str]:
    """piper invocation: a PATH binary when present, else `python -m piper` (works venv or not)."""
    binary = shutil.which("piper")
    return [binary] if binary else [sys.executable, "-m", "piper"]


def _write_narration(out_dir: Path, artefact: Any, warnings: list[str]) -> Path | None:
    """Synthesise per-scene narration with piper and concat to narration.wav, or warn and skip."""
    if not _TTS_MODEL.is_file():
        warnings.append(_NO_PIPER)
        return None
    base = _piper_base()
    config = ["-c", str(_TTS_CONFIG.resolve())] if _TTS_CONFIG.is_file() else []
    scene_wavs: list[Path] = []
    target = out_dir / "narration.wav"
    try:
        for index, scene in enumerate(artefact.scenes, 1):
            wav = out_dir / f"_nar_{index:02d}.wav"
            subprocess.run(
                [
                    *base,
                    "-m",
                    str(_TTS_MODEL.resolve()),
                    *config,
                    "--data-dir",
                    str(_TTS_DATA_DIR.resolve()),
                    "-f",
                    wav.name,
                ],
                input=scene.narration.encode("utf-8"),
                cwd=out_dir,
                capture_output=True,
                check=True,
            )
            scene_wavs.append(wav)
        listing = out_dir / "_nar_list.txt"
        listing.write_text("".join(f"file '{w.name}'\n" for w in scene_wavs), encoding="utf-8")
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
        detail = (
            exc.stderr.decode("utf-8", "replace")[-200:]
            if isinstance(exc, subprocess.CalledProcessError) and exc.stderr
            else ""
        )
        warnings.append(
            f"piper/ffmpeg narration failed ({type(exc).__name__}: {detail}) — {_NO_PIPER}"
        )
        return None
    return target if target.is_file() else None


def _cleanup(out_dir: Path) -> None:
    """Remove intermediate wav/list/srt/frame scratch files left by the media steps."""
    for pattern in _TEMP_GLOBS:
        for stale in out_dir.glob(pattern):
            stale.unlink(missing_ok=True)
