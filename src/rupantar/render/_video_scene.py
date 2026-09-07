"""Scene-type derivation, panel planning, infographic hero/chart panels, and b-roll frames.

The video schema has no ``scene_type`` field, so the type is a heuristic (documented as a
deviation): scene 0 -> ``title_card``; last scene -> ``closing``; a quoted scene -> ``quote``;
a scene with parseable numeric content -> ``stat_block``; the infographic-backed panel ->
``infographic_hero``; otherwise ``statement``.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from rupantar.render.charts import ChartData, extract_chart_data, parse_leading_number, render_chart
from rupantar.render.panels import render_panel
from rupantar.render.theme import Theme

Runner = Callable[..., Any]


def _run(runner: Runner | None, argv: list[str]) -> Any:
    """Invoke ``runner`` (or ``subprocess.run``) with the standard capture flags."""
    return (runner or subprocess.run)(argv, capture_output=True, check=True)


_QUOTE_CHARS = ('"', "“", "”", "‘", "’")
_STAT_UNIT = re.compile(
    r"\d[\d,]*(?:\.\d+)?\s*(%|percent|days?|hours?|minutes?|weeks?|months?|years?|"
    r"m|k|bn|million|billion|x)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PanelPlan:
    """One timeline item: a panel to render plus its duration, narration, and provenance."""

    index: int
    layout: str
    title: str
    body_lines: list[str]
    duration: int
    narration: str
    background: Path | None = None
    background_evidence: str = ""
    lower_third: tuple[str, str] = ("", "")
    is_extra: bool = False
    chart_data: ChartData | None = field(default=None, compare=False)


def reads_as_quote(text: str) -> bool:
    """True when the text contains a quotation mark."""
    return any(char in text for char in _QUOTE_CHARS)


def has_stat(text: str) -> bool:
    """True when the text leads with a number or carries a number-with-unit."""
    stripped = text.strip()
    if parse_leading_number(stripped) is not None and len(stripped.split()) <= 8:
        return True
    return bool(_STAT_UNIT.search(stripped))


def derive_scene_type(index: int, count: int, scene: Any) -> str:
    """Pick a panel layout for a scene from its position and text (heuristic, no schema field)."""
    if index == 0:
        return "title_card"
    if count > 1 and index == count - 1:
        return "closing"
    text = f"{scene.on_screen_text} {scene.scene_description}"
    if reads_as_quote(text):
        return "quote"
    if has_stat(scene.on_screen_text):
        return "stat_block"
    return "statement"


def _heading(scene: Any) -> str:
    """A short title derived from a scene's on-screen text."""
    first = re.split(r"(?<=[.!?])\s", scene.on_screen_text.strip(), maxsplit=1)[0]
    return first[:52].strip() or "Scene"


def _split_stat(text: str) -> list[str]:
    """Split ``"8 days to contain"`` into ``["8 days", "to contain"]``."""
    match = re.match(r"\s*([^A-Za-z]*\d[\d,.:%]*\s*[A-Za-z%]{0,10})\s*(.*)", text.strip())
    if match and match.group(1).strip():
        return [match.group(1).strip(), match.group(2).strip() or text.strip()]
    return [text.strip()[:12] or "--", text.strip()]


def _body_for(layout: str, scene: Any, logline: str) -> list[str]:
    """Layout-specific body lines for a scene panel."""
    if layout == "title_card":
        return [logline]
    if layout == "stat_block":
        return _split_stat(scene.on_screen_text)
    if layout in ("statement", "closing"):
        # the on-screen text is the title for these; no duplicate body line
        return []
    return [scene.on_screen_text or scene.scene_description]


def _title_for(layout: str, scene: Any, artefact: Any) -> str:
    """Layout-specific panel title."""
    if layout == "title_card":
        return str(getattr(artefact, "title", "") or "Video")
    if layout in ("statement", "closing"):
        return (scene.on_screen_text or scene.scene_description).strip()
    return _heading(scene)


def plan_panels(
    artefact: Any,
    theme: Theme,
    context: Any,
    scratch_dir: Path,
    warnings: list[str],
    *,
    runner: Runner | None = None,
) -> tuple[list[PanelPlan], list[dict[str, str]]]:
    """Build the ordered panel plan: scene panels + infographic extras + b-roll backgrounds."""
    scenes = list(artefact.scenes)
    count = len(scenes)
    lower = ("Video Package", "")
    plans: list[PanelPlan] = []
    for i, scene in enumerate(scenes):
        layout = derive_scene_type(i, count, scene)
        plans.append(
            PanelPlan(
                index=0,
                layout=layout,
                title=_title_for(layout, scene, artefact),
                body_lines=_body_for(layout, scene, artefact.logline),
                duration=max(1, int(scene.duration_seconds)),
                narration=scene.narration,
                lower_third=lower,
            )
        )
    extras = _infographic_panels(context, lower, warnings)
    ordered = [*plans[:1], *extras, *plans[1:]] if plans else extras
    ordered = [replace(plan, index=n) for n, plan in enumerate(ordered, 1)]
    return _assign_backgrounds(ordered, context, scratch_dir, warnings, runner)


def _infographic_panels(
    context: Any, lower: tuple[str, str], warnings: list[str]
) -> list[PanelPlan]:
    """A hero panel from the infographic spec plus a chart panel when numbers parse."""
    spec = getattr(context, "infographic_spec", None) if context is not None else None
    if spec is None:
        return []
    hero_body = [spec.subhead, *[section.stat_label for section in spec.sections]]
    panels = [
        PanelPlan(
            index=0,
            layout="infographic_hero",
            title=spec.headline,
            body_lines=hero_body,
            duration=6,
            narration="",
            lower_third=lower,
            is_extra=True,
        )
    ]
    data = extract_chart_data(spec)
    if data is not None:
        panels.append(
            PanelPlan(
                index=0,
                layout="chart",
                title=data.title or "Key figures",
                body_lines=[],
                duration=6,
                narration="",
                lower_third=lower,
                is_extra=True,
                chart_data=data,
            )
        )
    else:
        warnings.append("infographic spec had no parseable numeric data - no chart panel")
    return panels


def _source_for(name: str, context: Any) -> Path | None:
    """Match an evidence source_name to one of the request's original file paths."""
    for path in getattr(context, "source_paths", []) or []:
        candidate = Path(path)
        if candidate.name == name or candidate.stem == Path(name).stem:
            return candidate
    return None


def _assign_backgrounds(
    plans: list[PanelPlan],
    context: Any,
    scratch_dir: Path,
    warnings: list[str],
    runner: Runner | None,
) -> tuple[list[PanelPlan], list[dict[str, str]]]:
    """Attach real source frames as backgrounds to scene panels, round-robin by position."""
    dossier = getattr(context, "dossier", None) if context is not None else None
    if dossier is None:
        return plans, []
    candidates = _image_backgrounds(dossier, context) + _video_backgrounds(
        dossier, context, scratch_dir, warnings, runner
    )
    if not candidates:
        return plans, []
    targets = [i for i, plan in enumerate(plans) if not plan.is_extra]
    used: dict[str, dict[str, str]] = {}
    for slot, plan_index in enumerate(targets):
        evidence_id, name, kind, path = candidates[slot % len(candidates)]
        plans[plan_index] = replace(
            plans[plan_index], background=path, background_evidence=evidence_id
        )
        used[evidence_id] = {"evidence_id": evidence_id, "source_name": name, "kind": kind}
    return plans, list(used.values())


def _image_backgrounds(dossier: Any, context: Any) -> list[tuple[str, str, str, Path]]:
    """Usable image-source backgrounds: original file path + evidence id."""
    out: list[tuple[str, str, str, Path]] = []
    for insight in getattr(dossier, "image_insights", []) or []:
        path = _source_for(insight.source_name, context)
        if path is not None and path.is_file():
            out.append((insight.evidence_id or "?", insight.source_name, "image", path))
    return out


def _video_backgrounds(
    dossier: Any, context: Any, scratch_dir: Path, warnings: list[str], runner: Runner | None
) -> list[tuple[str, str, str, Path]]:
    """Extract one mid-span frame per video event; failures warn and are skipped."""
    out: list[tuple[str, str, str, Path]] = []
    for order, event in enumerate(getattr(dossier, "video_events", []) or []):
        src = _source_for(event.source_name, context)
        if src is None or not src.is_file():
            warnings.append(f"b-roll: source for {event.source_name!r} not found - no frame")
            continue
        mid = max(0.0, (float(event.start) + float(event.end)) / 2.0)
        target = scratch_dir / f"_frame_{event.evidence_id or order}.png"
        frame = extract_frame(src, mid, target, warnings, runner)
        if frame is not None:
            out.append((event.evidence_id or "?", event.source_name, "video", frame))
    return out


def extract_frame(
    src: Path,
    midpoint: float,
    target: Path,
    warnings: list[str],
    runner: Runner | None = None,
) -> Path | None:
    """Grab a single frame from ``src`` at ``midpoint`` seconds with ffmpeg, or warn and skip."""
    argv = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{midpoint:.2f}",
        "-i",
        str(src),
        "-frames:v",
        "1",
        "-q:v",
        "3",
        str(target),
    ]
    try:
        _run(runner, argv)
    except Exception as exc:  # noqa: BLE001 - degrade, never crash the job
        warnings.append(f"b-roll: frame extraction from {src.name!r} failed ({type(exc).__name__})")
        return None
    return target if target.is_file() else None


def render_plan_panel(target: Path, plan: PanelPlan, count: int, footer: str, theme: Theme) -> None:
    """Render one planned panel PNG (a thin adaptor onto ``panels.render_panel``)."""
    if plan.layout == "chart" and plan.chart_data is not None:
        render_chart(target, plan.chart_data, theme)
        return
    render_panel(
        target,
        layout=plan.layout,
        title=plan.title,
        body_lines=plan.body_lines,
        scene_index=plan.index,
        scene_count=count,
        footer=footer,
        theme=theme,
        background=plan.background,
        scrim=plan.background is not None,
        lower_third=plan.lower_third,
    )
