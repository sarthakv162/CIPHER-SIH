"""Markdown rendering for every artefact type: the universal fallback. Pure f-strings."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from rupantar.core.artefacts import ArtefactBase


def render_md(artefact: ArtefactBase, path: Path) -> None:
    """Write the artefact as clean Markdown to `path`."""
    builder = _BUILDERS[str(artefact.artefact_type)]  # type: ignore[attr-defined]
    path.write_text(builder(artefact).rstrip() + "\n", encoding="utf-8")


def _bullets(items: Iterable[Any]) -> str:
    """Render an iterable of strings as Markdown bullets."""
    return "\n".join(f"- {item}" for item in items)


def _head(artefact: Any) -> str:
    """Title heading plus an optional confidence-notes blockquote."""
    out = f"# {artefact.title}\n"
    if artefact.confidence_notes.strip():
        out += f"\n> Confidence: {artefact.confidence_notes.strip()}\n"
    return out


def _executive_summary(a: Any) -> str:
    return (
        f"{_head(a)}\n"
        f"**{a.headline}**\n\n"
        f"## Key points\n{_bullets(a.key_points)}\n\n"
        f"## Context\n{a.context}\n\n"
        f"## Implications\n{_bullets(a.implications)}\n\n"
        f"## Recommended actions\n{_bullets(a.recommended_actions)}\n\n"
        f"---\n\n_{a.one_line_takeaway}_\n"
    )


def _advisory(a: Any) -> str:
    details = "\n\n".join(f"### {d.heading}\n{d.body}" for d in a.technical_details)
    indicators = "\n".join(
        f"- `{i.ioc_type.value}` {i.value}" + (f" — {i.note}" if i.note else "")
        for i in a.indicators
    )
    actions = _bullets(f"**{r.priority.value}** — {r.action}" for r in a.recommended_actions)
    return (
        f"{_head(a)}\n"
        f"- **Advisory ID:** {a.advisory_id}\n"
        f"- **Severity:** {a.severity.value}\n"
        f"- **Issued for:** {a.issued_for}\n\n"
        f"## Summary\n{a.summary}\n\n"
        f"## Background\n{a.background}\n\n"
        f"## Technical details\n{details}\n\n"
        f"## Affected entities\n{_bullets(a.affected_entities) or '- none stated'}\n\n"
        f"## Indicators\n{indicators or '- none provided'}\n\n"
        f"## Recommended actions\n{actions}\n\n"
        f"## References\n{_bullets(a.references) or '- none'}\n\n"
        f"> Handling: {a.handling_caveat}\n"
    )


def _linkedin_post(a: Any) -> str:
    tags = " ".join(f"#{t}" for t in a.hashtags)
    return (
        f"{_head(a)}\n"
        f"_{a.hook}_\n\n"
        f"{a.body}\n\n"
        f"{a.call_to_action}\n\n"
        f"{tags}\n\n"
        f"---\n\n**Suggested image:** {a.suggested_image_brief}\n"
    )


def _x_thread(a: Any) -> str:
    posts = "\n\n".join(f"{i}/ {t.text}" for i, t in enumerate(a.tweets, 1))
    tags = " ".join(f"#{t}" for t in a.hashtags)
    return f"{_head(a)}\n_{a.thread_hook}_\n\n{posts}\n\n{tags}\n"


def _presentation(a: Any) -> str:
    slides = []
    for i, s in enumerate(a.slides, 1):
        block = f"## Slide {i}: {s.title}\n\n_Layout: {s.layout.value}_\n\n{_bullets(s.bullets)}"
        block += f"\n\n> Speaker notes: {s.speaker_notes}"
        slides.append(block)
    body = "\n\n".join(slides)
    return f"{_head(a)}\n{a.deck_summary}\n\n{body}\n"


def _infographic_spec(a: Any) -> str:
    sections = "\n\n".join(
        f"### {s.heading}\n**{s.stat_value}** — {s.stat_label}\n\n{s.body}" for s in a.sections
    )
    return (
        f"{_head(a)}\n"
        f"**{a.headline}**\n\n{a.subhead}\n\n"
        f"_Layout: {a.layout_recommendation.value}_\n\n"
        f"## Stat blocks\n{sections}\n\n"
        f"## Key messages\n{_bullets(a.key_messages)}\n\n"
        f"## Colour intent\n{a.colour_intent}\n\n"
        f"## Icon suggestions\n{_bullets(a.icon_suggestions)}\n\n"
        f"> {a.footer}\n"
    )


def _video_package(a: Any) -> str:
    scenes = []
    for i, s in enumerate(a.scenes, 1):
        scenes.append(
            f"### Scene {i} ({s.duration_seconds}s)\n"
            f"{s.scene_description}\n\n"
            f"**On screen:** {s.on_screen_text}\n\n"
            f"**Narration:** {s.narration}\n\n"
            f"**Visual:** {s.visual_recommendation}\n\n"
            f"**B-roll:** {', '.join(s.b_roll_suggestions)}"
        )
    body = "\n\n".join(scenes)
    return (
        f"{_head(a)}\n"
        f"_{a.logline}_\n\n"
        f"Target runtime: {a.runtime_seconds_target}s\n\n"
        f"## Scenes\n{body}\n\n"
        f"## Full narration\n{a.full_narration}\n\n"
        f"> Subtitles: {a.subtitle_hint}\n"
    )


_BUILDERS: dict[str, Any] = {
    "executive_summary": _executive_summary,
    "advisory": _advisory,
    "linkedin_post": _linkedin_post,
    "x_thread": _x_thread,
    "presentation": _presentation,
    "infographic_spec": _infographic_spec,
    "video_package": _video_package,
}
