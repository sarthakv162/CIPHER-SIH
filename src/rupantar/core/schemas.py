"""Frozen request and job contracts. See docs/SCHEMAS.md. Frozen at the end of Phase 0."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class ArtefactType(Enum):
    """The seven communication artefacts Rupantar can produce."""

    executive_summary = "executive_summary"
    advisory = "advisory"
    linkedin_post = "linkedin_post"
    x_thread = "x_thread"
    presentation = "presentation"
    infographic_spec = "infographic_spec"
    video_package = "video_package"


class JobStatus(Enum):
    """Lifecycle states for a single artefact job."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SourceKind(Enum):
    """Whether a source is inline text or a path on disk."""

    text = "text"
    file = "file"


class Audience(Enum):
    """Intended reader of the artefact."""

    general_public = "general_public"
    technical = "technical"
    executive = "executive"
    policy_maker = "policy_maker"
    media = "media"
    internal = "internal"


class Tone(Enum):
    """Register the artefact should adopt."""

    neutral = "neutral"
    formal = "formal"
    urgent = "urgent"
    reassuring = "reassuring"
    promotional = "promotional"
    analytical = "analytical"


class Detail(Enum):
    """How much depth the artefact should carry."""

    brief = "brief"
    standard = "standard"
    deep = "deep"


class Objective(Enum):
    """Communicative goal of the artefact."""

    inform = "inform"
    warn = "warn"
    persuade = "persuade"
    instruct = "instruct"
    announce = "announce"
    summarise = "summarise"


class Style(Enum):
    """Prose style for the artefact."""

    plain = "plain"
    narrative = "narrative"
    bulleted = "bulleted"
    technical = "technical"


class SourceInput(BaseModel):
    """One source of information: exactly one of `text` or `path` is set."""

    kind: SourceKind
    text: str | None = None
    path: str | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> SourceInput:
        """Enforce exactly one of text/path, consistent with `kind`."""
        has_text = self.text is not None
        has_path = self.path is not None
        if has_text == has_path:
            raise ValueError("SourceInput requires exactly one of 'text' or 'path'")
        if self.kind is SourceKind.text and not has_text:
            raise ValueError("kind='text' requires the 'text' field")
        if self.kind is SourceKind.file and not has_path:
            raise ValueError("kind='file' requires the 'path' field")
        return self


class GenerationParams(BaseModel):
    """Operator-chosen knobs that steer every artefact in a request."""

    audience: Audience = Audience.general_public
    tone: Tone = Tone.neutral
    language: str = "en"
    detail: Detail = Detail.standard
    objective: Objective = Objective.inform
    style: Style = Style.plain


class TransformRequest(BaseModel):
    """One operator request (a Transform / batch): sources in, artefact types out."""

    sources: list[SourceInput] = Field(min_length=1)
    output_types: list[ArtefactType] = Field(min_length=1)
    params: GenerationParams = Field(default_factory=GenerationParams)

    @field_validator("output_types")
    @classmethod
    def _dedup_preserve_order(cls, value: list[ArtefactType]) -> list[ArtefactType]:
        """Drop duplicate output types while keeping first-seen order."""
        seen: set[ArtefactType] = set()
        out: list[ArtefactType] = []
        for item in value:
            if item not in seen:
                seen.add(item)
                out.append(item)
        return out


class Job(BaseModel):
    """One artefact within a Transform. `transform_id` links it to the batch."""

    id: str
    transform_id: str
    artefact_type: ArtefactType
    model_key: str
    status: JobStatus
    depends_on: list[str] = Field(default_factory=list)
    error: str | None = None
    artefact_path: str | None = None
    created_at: datetime
    updated_at: datetime


class TextBlock(BaseModel):
    """Extracted plain text from one textual source."""

    source_name: str
    text: str


class ImageInsight(BaseModel):
    """What the VLM saw in one image source."""

    source_name: str
    caption: str
    extracted_text: str
    notable_elements: list[str] = Field(default_factory=list)


class TranscriptSegment(BaseModel):
    """One timed span of a transcript."""

    start: float
    end: float
    text: str


class Transcript(BaseModel):
    """Full transcript plus timed segments for one audio/video source."""

    source_name: str
    text: str
    segments: list[TranscriptSegment] = Field(default_factory=list)


class SourceDossier(BaseModel):
    """All ingested source material for one Transform, reduced to text."""

    id: str
    created_at: datetime
    sha256: str
    text_blocks: list[TextBlock] = Field(default_factory=list)
    image_insights: list[ImageInsight] = Field(default_factory=list)
    transcripts: list[Transcript] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    def to_prompt_text(self) -> str:
        """Flatten every block, caption, and transcript into one prompt-ready string."""
        parts: list[str] = []
        for block in self.text_blocks:
            parts.append(f"# Source: {block.source_name}\n{block.text}")
        for insight in self.image_insights:
            extra = f"\nText in image: {insight.extracted_text}" if insight.extracted_text else ""
            parts.append(f"# Image: {insight.source_name}\n{insight.caption}{extra}")
        for transcript in self.transcripts:
            parts.append(f"# Transcript: {transcript.source_name}\n{transcript.text}")
        return "\n\n".join(parts)
