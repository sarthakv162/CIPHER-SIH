"""The artefact field validators reject out-of-bound and empty content."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from rupantar.core.artefacts import (
    ARTEFACT_MODELS,
    Advisory,
    ExecutiveSummary,
    InfographicSpec,
    LinkedInPost,
    Presentation,
    VideoPackage,
    XThread,
)


def _load(artefacts_dir: Path, name: str) -> dict:
    return json.loads((artefacts_dir / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(ARTEFACT_MODELS))
def test_blank_title_rejected(artefacts_dir: Path, name: str) -> None:
    data = _load(artefacts_dir, name)
    data["title"] = "   "
    with pytest.raises(ValidationError):
        ARTEFACT_MODELS[name].model_validate(data)


@pytest.mark.parametrize("name", sorted(ARTEFACT_MODELS))
def test_empty_confidence_notes_allowed(artefacts_dir: Path, name: str) -> None:
    data = _load(artefacts_dir, name)
    data["confidence_notes"] = ""
    ARTEFACT_MODELS[name].model_validate(data)


def test_executive_summary_key_point_bounds(artefacts_dir: Path) -> None:
    data = _load(artefacts_dir, "executive_summary")
    data["key_points"] = data["key_points"][:2]
    with pytest.raises(ValidationError):
        ExecutiveSummary.model_validate(data)
    data["key_points"] = ["point"] * 7
    with pytest.raises(ValidationError):
        ExecutiveSummary.model_validate(data)


def test_executive_summary_allows_zero_recommended_actions(artefacts_dir: Path) -> None:
    data = _load(artefacts_dir, "executive_summary")
    data["recommended_actions"] = []
    ExecutiveSummary.model_validate(data)


def test_advisory_requires_technical_details_and_actions(artefacts_dir: Path) -> None:
    data = _load(artefacts_dir, "advisory")
    data["technical_details"] = []
    with pytest.raises(ValidationError):
        Advisory.model_validate(data)

    data = _load(artefacts_dir, "advisory")
    data["recommended_actions"] = []
    with pytest.raises(ValidationError):
        Advisory.model_validate(data)


def test_advisory_allows_empty_indicators_and_references(artefacts_dir: Path) -> None:
    data = _load(artefacts_dir, "advisory")
    data["indicators"] = []
    data["references"] = []
    Advisory.model_validate(data)


def test_advisory_rejects_bad_enums(artefacts_dir: Path) -> None:
    data = _load(artefacts_dir, "advisory")
    data["severity"] = "catastrophic"
    with pytest.raises(ValidationError):
        Advisory.model_validate(data)

    data = _load(artefacts_dir, "advisory")
    data["recommended_actions"][0]["priority"] = "asap"
    with pytest.raises(ValidationError):
        Advisory.model_validate(data)

    data = _load(artefacts_dir, "advisory")
    data["indicators"][0]["type"] = "cidr"
    with pytest.raises(ValidationError):
        Advisory.model_validate(data)


def test_advisory_indicator_alias_and_name_both_parse(artefacts_dir: Path) -> None:
    data = _load(artefacts_dir, "advisory")
    data["indicators"][0] = {"ioc_type": "url", "value": "http://bad.example/x", "note": ""}
    advisory = Advisory.model_validate(data)
    assert advisory.indicators[0].ioc_type.value == "url"
    assert advisory.model_dump(mode="json", by_alias=True)["indicators"][0]["type"] == "url"


def test_linkedin_body_limit(artefacts_dir: Path) -> None:
    data = _load(artefacts_dir, "linkedin_post")
    data["body"] = "x" * 2801
    with pytest.raises(ValidationError):
        LinkedInPost.model_validate(data)


def test_linkedin_hashtag_rules(artefacts_dir: Path) -> None:
    data = _load(artefacts_dir, "linkedin_post")
    data["hashtags"] = ["OnlyOne", "Two"]
    with pytest.raises(ValidationError):
        LinkedInPost.model_validate(data)

    data = _load(artefacts_dir, "linkedin_post")
    data["hashtags"] = ["#Hashed", "Fine", "AlsoFine"]
    with pytest.raises(ValidationError):
        LinkedInPost.model_validate(data)


def test_xthread_bounds(artefacts_dir: Path) -> None:
    data = _load(artefacts_dir, "x_thread")
    data["tweets"] = data["tweets"][:2]
    with pytest.raises(ValidationError):
        XThread.model_validate(data)

    data = _load(artefacts_dir, "x_thread")
    data["tweets"][0]["text"] = "y" * 276
    with pytest.raises(ValidationError):
        XThread.model_validate(data)

    data = _load(artefacts_dir, "x_thread")
    data["hashtags"] = ["a", "b", "c", "d"]
    with pytest.raises(ValidationError):
        XThread.model_validate(data)


def test_presentation_slide_bounds(artefacts_dir: Path) -> None:
    data = _load(artefacts_dir, "presentation")
    data["slides"] = data["slides"][:4]
    with pytest.raises(ValidationError):
        Presentation.model_validate(data)

    data = _load(artefacts_dir, "presentation")
    data["slides"][0]["layout"] = "sidebar"
    with pytest.raises(ValidationError):
        Presentation.model_validate(data)


def test_infographic_bounds(artefacts_dir: Path) -> None:
    data = _load(artefacts_dir, "infographic_spec")
    data["sections"] = data["sections"][:2]
    with pytest.raises(ValidationError):
        InfographicSpec.model_validate(data)

    data = _load(artefacts_dir, "infographic_spec")
    data["key_messages"] = ["only one"]
    with pytest.raises(ValidationError):
        InfographicSpec.model_validate(data)

    data = _load(artefacts_dir, "infographic_spec")
    data["layout_recommendation"] = "spiral"
    with pytest.raises(ValidationError):
        InfographicSpec.model_validate(data)


def test_infographic_stat_value_is_string(artefacts_dir: Path) -> None:
    data = _load(artefacts_dir, "infographic_spec")
    spec = InfographicSpec.model_validate(data)
    assert all(isinstance(s.stat_value, str) for s in spec.sections)


def test_video_scene_bounds(artefacts_dir: Path) -> None:
    data = _load(artefacts_dir, "video_package")
    data["scenes"] = data["scenes"][:3]
    with pytest.raises(ValidationError):
        VideoPackage.model_validate(data)

    data = _load(artefacts_dir, "video_package")
    data["scenes"] = data["scenes"] + data["scenes"] + data["scenes"]  # 12 > 8
    with pytest.raises(ValidationError):
        VideoPackage.model_validate(data)


def test_video_runtime_scene_sum_mismatch_is_allowed(artefacts_dir: Path) -> None:
    data = _load(artefacts_dir, "video_package")
    data["runtime_seconds_target"] = 5
    VideoPackage.model_validate(data)
