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
    # A free string, not an enum: templates are declared in configs/templates/templates.yaml,
    # data the schema must not need a code change to grow. An unknown id degrades gracefully
    # to the built-in renderer (render/pptx_render.py, render/docx_render.py) rather than
    # failing validation here.
    template: str = "ntro-formal"


class TransformRequest(BaseModel):
    """One operator request (a Transform / batch): sources in, artefact types out."""

    sources: list[SourceInput] = Field(min_length=1)
    output_types: list[ArtefactType] = Field(min_length=1)
    params: GenerationParams = Field(default_factory=GenerationParams)
    operator: str | None = None

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
    """Extracted plain text from one textual source. `evidence_id` set at dossier assembly."""

    source_name: str
    text: str
    evidence_id: str = ""
    page: int | None = None
    heading: str = ""


class ImageInsight(BaseModel):
    """What the VLM saw in one image source. `evidence_id` set at dossier assembly."""

    source_name: str
    caption: str
    extracted_text: str
    notable_elements: list[str] = Field(default_factory=list)
    evidence_id: str = ""


class TranscriptSegment(BaseModel):
    """One timed span of a transcript. `evidence_id` set at dossier assembly."""

    start: float
    end: float
    text: str
    evidence_id: str = ""


class Transcript(BaseModel):
    """Full transcript plus timed segments for one audio/video source."""

    source_name: str
    text: str
    segments: list[TranscriptSegment] = Field(default_factory=list)


class VideoEvent(BaseModel):
    """A timestamped span of a video: a transcript slice paired with a keyframe caption."""

    source_name: str
    start: float
    end: float
    transcript: str = ""
    caption: str = ""
    evidence_id: str = ""


def _mmss(seconds: float) -> str:
    """Format a second offset as m:ss (or h:mm:ss past an hour)."""
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


class SourceDossier(BaseModel):
    """All ingested source material for one Transform, reduced to text with evidence IDs."""

    id: str
    created_at: datetime
    sha256: str
    text_blocks: list[TextBlock] = Field(default_factory=list)
    image_insights: list[ImageInsight] = Field(default_factory=list)
    transcripts: list[Transcript] = Field(default_factory=list)
    video_events: list[VideoEvent] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    def to_prompt_text(self) -> str:
        """Flatten every evidence unit into one prompt-ready string, each tagged `[En]`."""
        parts: list[str] = [self._text_part(b) for b in self.text_blocks]
        parts += [self._image_part(i) for i in self.image_insights]
        parts += [self._video_part(e) for e in self.video_events]
        for transcript in self.transcripts:
            if transcript.segments:
                parts += [self._audio_part(transcript.source_name, s) for s in transcript.segments]
            else:
                parts.append(f"Audio: {transcript.source_name}\n{transcript.text}")
        return "\n\n".join(parts)

    @staticmethod
    def _text_part(block: TextBlock) -> str:
        """One `[En]`-tagged text block, with page and heading when known."""
        loc = f" (p.{block.page})" if block.page else ""
        head = f" — {block.heading}" if block.heading else ""
        return f"[{block.evidence_id or '?'}] Source: {block.source_name}{loc}{head}\n{block.text}"

    @staticmethod
    def _image_part(insight: ImageInsight) -> str:
        """One `[En]`-tagged image caption."""
        extra = f"\nText in image: {insight.extracted_text}" if insight.extracted_text else ""
        tag = insight.evidence_id or "?"
        return f"[{tag}] Image: {insight.source_name}\n{insight.caption}{extra}"

    @staticmethod
    def _video_part(event: VideoEvent) -> str:
        """One `[En]`-tagged video event with an m:ss–m:ss span."""
        span = f"{_mmss(event.start)}–{_mmss(event.end)}"
        lines = [f"[{event.evidence_id or '?'}] Video: {event.source_name} {span}"]
        if event.transcript:
            lines.append(f"Transcript: {event.transcript}")
        if event.caption:
            lines.append(f"Visual: {event.caption}")
        return "\n".join(lines)

    @staticmethod
    def _audio_part(source_name: str, segment: TranscriptSegment) -> str:
        """One `[En]`-tagged transcript segment with an m:ss–m:ss span."""
        span = f"{_mmss(segment.start)}–{_mmss(segment.end)}"
        return f"[{segment.evidence_id or '?'}] Audio: {source_name} {span}\n{segment.text}"
