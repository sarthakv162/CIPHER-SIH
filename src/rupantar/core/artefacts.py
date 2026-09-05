"""Frozen artefact contracts: one Pydantic model per artefact type. Frozen at end of Phase 0.

Array order is the order: list items carry no `index` field. Every stated list bound and
character limit is enforced in a validator here, not merely documented in docs/SCHEMAS.md.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

_T = TypeVar("_T")


def _reject_blank(value: str) -> str:
    """Reject a string that is empty or whitespace-only."""
    if not value.strip():
        raise ValueError("must not be empty")
    return value


NonEmptyStr = Annotated[str, AfterValidator(_reject_blank)]


def _len_between(value: list[_T], low: int, high: int, name: str) -> list[_T]:
    """Return `value` unchanged if its length is within [low, high], else raise."""
    if not low <= len(value) <= high:
        raise ValueError(f"{name} must have {low}-{high} entries, got {len(value)}")
    return value


def _min_len(value: list[_T], low: int, name: str) -> list[_T]:
    """Return `value` unchanged if it has at least `low` entries, else raise."""
    if len(value) < low:
        raise ValueError(f"{name} must have at least {low} entries, got {len(value)}")
    return value


class Severity(Enum):
    """Advisory severity band."""

    informational = "informational"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IocType(Enum):
    """Indicator-of-compromise type. Serialised under the JSON key `type`."""

    ipv4 = "ipv4"
    ipv6 = "ipv6"
    domain = "domain"
    url = "url"
    sha256 = "sha256"
    md5 = "md5"
    email = "email"
    filename = "filename"
    other = "other"


class ActionPriority(Enum):
    """Priority of a recommended action in an advisory."""

    immediate = "immediate"
    high = "high"
    medium = "medium"
    low = "low"


class SlideLayout(Enum):
    """Layout of a single presentation slide."""

    title = "title"
    bullets = "bullets"
    two_column = "two_column"
    quote = "quote"
    closing = "closing"


class InfographicLayout(Enum):
    """Overall arrangement recommendation for an infographic."""

    vertical_flow = "vertical_flow"
    three_column = "three_column"
    timeline = "timeline"
    comparison = "comparison"
    hub_spoke = "hub_spoke"


class ArtefactBase(BaseModel):
    """Shared head of every artefact. `confidence_notes` may be empty; nothing else may."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    title: NonEmptyStr
    confidence_notes: str = ""


class ExecutiveSummary(ArtefactBase):
    """A decision-maker's one-page read of the source."""

    artefact_type: Literal["executive_summary"] = "executive_summary"
    headline: NonEmptyStr
    key_points: list[NonEmptyStr]
    context: NonEmptyStr
    implications: list[NonEmptyStr]
    recommended_actions: list[NonEmptyStr]
    one_line_takeaway: NonEmptyStr

    @field_validator("key_points")
    @classmethod
    def _check_key_points(cls, v: list[str]) -> list[str]:
        """key_points: 3-6 entries."""
        return _len_between(list(v), 3, 6, "key_points")

    @field_validator("implications")
    @classmethod
    def _check_implications(cls, v: list[str]) -> list[str]:
        """implications: 2-4 entries."""
        return _len_between(list(v), 2, 4, "implications")

    @field_validator("recommended_actions")
    @classmethod
    def _check_actions(cls, v: list[str]) -> list[str]:
        """recommended_actions: 0-5 entries."""
        return _len_between(list(v), 0, 5, "recommended_actions")


class TechnicalDetail(BaseModel):
    """One titled block of technical explanation in an advisory."""

    model_config = ConfigDict(extra="forbid")

    heading: NonEmptyStr
    body: NonEmptyStr


class Indicator(BaseModel):
    """One indicator of compromise. Python field `ioc_type`, JSON key `type`."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    ioc_type: IocType = Field(alias="type")
    value: NonEmptyStr
    note: str = ""


class RecommendedAction(BaseModel):
    """One prioritised action in an advisory."""

    model_config = ConfigDict(extra="forbid")

    priority: ActionPriority
    action: NonEmptyStr


class Advisory(ArtefactBase):
    """A security or policy advisory with indicators and prioritised actions."""

    artefact_type: Literal["advisory"] = "advisory"
    advisory_id: NonEmptyStr
    severity: Severity
    issued_for: NonEmptyStr
    summary: NonEmptyStr
    background: NonEmptyStr
    technical_details: list[TechnicalDetail]
    affected_entities: list[NonEmptyStr]
    indicators: list[Indicator]
    recommended_actions: list[RecommendedAction]
    references: list[NonEmptyStr]
    handling_caveat: NonEmptyStr

    @field_validator("technical_details")
    @classmethod
    def _check_technical_details(cls, v: list[TechnicalDetail]) -> list[TechnicalDetail]:
        """technical_details: at least 1 entry."""
        return _min_len(list(v), 1, "technical_details")

    @field_validator("recommended_actions")
    @classmethod
    def _check_recommended_actions(cls, v: list[RecommendedAction]) -> list[RecommendedAction]:
        """recommended_actions: at least 1 entry."""
        return _min_len(list(v), 1, "recommended_actions")


class LinkedInPost(ArtefactBase):
    """A single LinkedIn post with hook, body, hashtags, and CTA."""

    artefact_type: Literal["linkedin_post"] = "linkedin_post"
    body: NonEmptyStr
    hook: NonEmptyStr
    hashtags: list[NonEmptyStr]
    call_to_action: NonEmptyStr
    suggested_image_brief: NonEmptyStr

    @field_validator("body")
    @classmethod
    def _check_body_len(cls, v: str) -> str:
        """body: at most 2800 characters."""
        if len(v) > 2800:
            raise ValueError(f"body must be <= 2800 chars, got {len(v)}")
        return v

    @field_validator("hashtags")
    @classmethod
    def _check_hashtags(cls, v: list[str]) -> list[str]:
        """hashtags: 3-6 entries, none starting with '#'."""
        _len_between(list(v), 3, 6, "hashtags")
        for tag in v:
            if tag.startswith("#"):
                raise ValueError(f"hashtag {tag!r} must not start with '#'")
        return v


class Tweet(BaseModel):
    """One post in an X thread."""

    model_config = ConfigDict(extra="forbid")

    text: NonEmptyStr

    @field_validator("text")
    @classmethod
    def _check_text_len(cls, v: str) -> str:
        """tweet text: at most 275 characters."""
        if len(v) > 275:
            raise ValueError(f"tweet text must be <= 275 chars, got {len(v)}")
        return v


class XThread(ArtefactBase):
    """A short X/Twitter thread."""

    artefact_type: Literal["x_thread"] = "x_thread"
    tweets: list[Tweet]
    hashtags: list[NonEmptyStr]
    thread_hook: NonEmptyStr

    @field_validator("tweets")
    @classmethod
    def _check_tweets(cls, v: list[Tweet]) -> list[Tweet]:
        """tweets: 3-8 entries."""
        return _len_between(list(v), 3, 8, "tweets")

    @field_validator("hashtags")
    @classmethod
    def _check_hashtags(cls, v: list[str]) -> list[str]:
        """hashtags: 1-3 entries."""
        return _len_between(list(v), 1, 3, "hashtags")


class Slide(BaseModel):
    """One presentation slide."""

    model_config = ConfigDict(extra="forbid")

    layout: SlideLayout
    title: NonEmptyStr
    bullets: list[NonEmptyStr]
    speaker_notes: NonEmptyStr


class Presentation(ArtefactBase):
    """A slide deck with speaker notes."""

    artefact_type: Literal["presentation"] = "presentation"
    slides: list[Slide]
    deck_summary: NonEmptyStr

    @field_validator("slides")
    @classmethod
    def _check_slides(cls, v: list[Slide]) -> list[Slide]:
        """slides: 5-12 entries."""
        return _len_between(list(v), 5, 12, "slides")


class InfographicSection(BaseModel):
    """One stat block in an infographic."""

    model_config = ConfigDict(extra="forbid")

    heading: NonEmptyStr
    stat_value: NonEmptyStr
    stat_label: NonEmptyStr
    body: NonEmptyStr


class InfographicSpec(ArtefactBase):
    """A layout-and-copy specification for an infographic."""

    artefact_type: Literal["infographic_spec"] = "infographic_spec"
    headline: NonEmptyStr
    subhead: NonEmptyStr
    sections: list[InfographicSection]
    key_messages: list[NonEmptyStr]
    layout_recommendation: InfographicLayout
    colour_intent: NonEmptyStr
    icon_suggestions: list[NonEmptyStr]
    footer: NonEmptyStr

    @field_validator("sections")
    @classmethod
    def _check_sections(cls, v: list[InfographicSection]) -> list[InfographicSection]:
        """sections: 3-5 entries."""
        return _len_between(list(v), 3, 5, "sections")

    @field_validator("key_messages")
    @classmethod
    def _check_key_messages(cls, v: list[str]) -> list[str]:
        """key_messages: 2-4 entries."""
        return _len_between(list(v), 2, 4, "key_messages")


class Scene(BaseModel):
    """One scene in a video package."""

    model_config = ConfigDict(extra="forbid")

    duration_seconds: int = Field(gt=0)
    scene_description: NonEmptyStr
    on_screen_text: NonEmptyStr
    narration: NonEmptyStr
    visual_recommendation: NonEmptyStr
    b_roll_suggestions: list[NonEmptyStr]


class VideoPackage(ArtefactBase):
    """A short-video plan: scenes, narration, and subtitle guidance."""

    artefact_type: Literal["video_package"] = "video_package"
    runtime_seconds_target: int = Field(gt=0)
    logline: NonEmptyStr
    scenes: list[Scene]
    full_narration: NonEmptyStr
    subtitle_hint: NonEmptyStr

    @field_validator("scenes")
    @classmethod
    def _check_scenes(cls, v: list[Scene]) -> list[Scene]:
        """scenes: 4-8 entries."""
        return _len_between(list(v), 4, 8, "scenes")


ARTEFACT_MODELS: dict[str, type[ArtefactBase]] = {
    "executive_summary": ExecutiveSummary,
    "advisory": Advisory,
    "linkedin_post": LinkedInPost,
    "x_thread": XThread,
    "presentation": Presentation,
    "infographic_spec": InfographicSpec,
    "video_package": VideoPackage,
}
