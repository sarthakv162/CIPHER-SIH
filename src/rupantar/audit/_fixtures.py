"""In-code sample inputs for selfcheck checks 6 and 7 (no dependency on tests/)."""

from __future__ import annotations

from pathlib import Path

from rupantar.core.artefacts import (
    Advisory,
    ArtefactBase,
    ExecutiveSummary,
    InfographicSpec,
    LinkedInPost,
    Presentation,
    VideoPackage,
    XThread,
)

_LOREM = "Selfcheck sample content for renderer verification only."


def _executive_summary() -> ExecutiveSummary:
    return ExecutiveSummary(
        title="Selfcheck Summary",
        headline="A short headline",
        key_points=["one", "two", "three"],
        context=_LOREM,
        implications=["first", "second"],
        recommended_actions=["act"],
        one_line_takeaway="Everything renders.",
    )


def _advisory() -> Advisory:
    return Advisory(
        title="Selfcheck Advisory",
        advisory_id="RUP-SC-1",
        severity="medium",
        issued_for="operators",
        summary=_LOREM,
        background=_LOREM,
        technical_details=[{"heading": "Detail", "body": _LOREM}],
        affected_entities=["system"],
        indicators=[{"type": "ipv4", "value": "198.51.100.1"}],
        recommended_actions=[{"priority": "high", "action": "patch"}],
        references=["https://example.invalid/ref"],
        handling_caveat="TLP:CLEAR",
    )


def _linkedin_post() -> LinkedInPost:
    return LinkedInPost(
        title="Selfcheck Post",
        hook="A hook line.",
        body=_LOREM,
        hashtags=["airgap", "offline", "rupantar"],
        call_to_action="Read more.",
        suggested_image_brief="A laptop with no network cable.",
    )


def _x_thread() -> XThread:
    return XThread(
        title="Selfcheck Thread",
        thread_hook="A thread hook.",
        tweets=[{"text": "one"}, {"text": "two"}, {"text": "three"}],
        hashtags=["offline"],
    )


def _presentation() -> Presentation:
    return Presentation(
        title="Selfcheck Deck",
        deck_summary=_LOREM,
        slides=[
            {
                "layout": "title",
                "title": f"Slide {i}",
                "bullets": ["a", "b"],
                "speaker_notes": _LOREM,
            }
            for i in range(1, 6)
        ],
    )


def _infographic_spec() -> InfographicSpec:
    return InfographicSpec(
        title="Selfcheck Infographic",
        headline="Headline",
        subhead="Subhead",
        sections=[
            {"heading": f"S{i}", "stat_value": "42%", "stat_label": "label", "body": _LOREM}
            for i in range(1, 4)
        ],
        key_messages=["msg one", "msg two"],
        layout_recommendation="three_column",
        colour_intent="calm blues",
        icon_suggestions=["lock", "shield"],
        footer="Rupantar selfcheck",
    )


def _video_package() -> VideoPackage:
    return VideoPackage(
        title="Selfcheck Video",
        runtime_seconds_target=8,
        logline="A tiny selfcheck clip.",
        scenes=[
            {
                "duration_seconds": 2,
                "scene_description": _LOREM,
                "on_screen_text": f"Scene {i}",
                "narration": "Narration line.",
                "visual_recommendation": "static panel",
                "b_roll_suggestions": ["none"],
            }
            for i in range(1, 5)
        ],
        full_narration="Narration line. Narration line. Narration line. Narration line.",
        subtitle_hint="one line per scene",
    )


def sample_artefacts() -> dict[str, ArtefactBase]:
    """One minimal, schema-valid instance of every artefact type."""
    return {
        "executive_summary": _executive_summary(),
        "advisory": _advisory(),
        "linkedin_post": _linkedin_post(),
        "x_thread": _x_thread(),
        "presentation": _presentation(),
        "infographic_spec": _infographic_spec(),
        "video_package": _video_package(),
    }


_IOC_CSV = "type,value\nipv4,198.51.100.23\ndomain,evil.example.com\n"
_PLAIN_CSV = "id,name\n1,alpha\n2,beta\n"
_SIGMA = (
    "title: Selfcheck Rule\n"
    "logsource:\n  product: windows\n  category: process_creation\n"
    "detection:\n  selection:\n    Image: '*/powershell.exe'\n  condition: selection\n"
)
_CEF = "CEF:0|Security|Selfcheck|1.0|100|Test Event|3|src=10.0.0.1 dst=10.0.0.2 act=block\n"


def write_converter_samples(dest: Path) -> dict[str, Path]:
    """Write tiny converter inputs into `dest`; return {logical_name: path}."""
    dest.mkdir(parents=True, exist_ok=True)
    paths = {
        "csv": dest / "plain.csv",
        "ioc-csv": dest / "iocs.csv",
        "sigma": dest / "rule.yml",
        "cef": dest / "events.cef",
    }
    paths["csv"].write_text(_PLAIN_CSV, encoding="utf-8")
    paths["ioc-csv"].write_text(_IOC_CSV, encoding="utf-8")
    paths["sigma"].write_text(_SIGMA, encoding="utf-8")
    paths["cef"].write_text(_CEF, encoding="utf-8")
    return paths
