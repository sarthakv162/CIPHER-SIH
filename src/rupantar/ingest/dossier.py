"""Assemble one SourceDossier from mixed sources: text, then vision, then audio."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from rupantar.core.schemas import (
    ImageInsight,
    SourceDossier,
    SourceInput,
    SourceKind,
    TextBlock,
    Transcript,
    TranscriptSegment,
    VideoEvent,
)
from rupantar.ingest.audio import transcribe
from rupantar.ingest.image import caption_image
from rupantar.ingest.text import extract_blocks
from rupantar.ingest.video import Keyframe, extract_audio, keyframes, probe_duration
from rupantar.models.client import LlamaClient
from rupantar.models.manager import ModelManager

_TEXT = {".pdf", ".docx", ".html", ".htm", ".md", ".markdown", ".txt"}
_IMAGE = {".png", ".jpg", ".jpeg", ".webp"}
_AUDIO = {".wav", ".mp3", ".m4a", ".flac"}
_VIDEO = {".mp4", ".mov", ".mkv"}


@dataclass
class _Bucket:
    """Sources sorted by modality plus the text blocks of the model-free first pass."""

    text_blocks: list[TextBlock] = field(default_factory=list)
    images: list[Path] = field(default_factory=list)
    audio: list[Path] = field(default_factory=list)
    videos: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class _VideoMedia:
    """The ffmpeg-derived material for one video source, before captioning or transcription."""

    name: str
    frames: list[Keyframe]
    wav: Path | None
    duration: float


async def assemble_dossier(
    sources: list[SourceInput],
    *,
    manager: ModelManager,
    out_dir: Path,
    new_id: Callable[[], str],
    clock: Callable[[], datetime],
    language: str = "en",
) -> tuple[SourceDossier, list[str]]:
    """Reduce every source to text: caption images and keyframes, then transcribe audio."""
    bucket = _classify(sources)
    warnings = bucket.warnings
    videos = _prepare_media(bucket, out_dir, warnings)

    image_insights, captioned = await _run_vision(bucket.images, videos, manager, warnings)
    transcripts, video_segments = await _run_audio(bucket.audio, videos, manager, warnings)

    video_events: list[VideoEvent] = []
    for media in videos:
        segments = video_segments.get(media.name, [])
        total = max(media.duration, segments[-1].end if segments else 0.0)
        video_events.extend(
            _build_video_events(media.name, captioned.get(media.name, []), segments, total)
        )

    _assign_evidence_ids(bucket.text_blocks, image_insights, video_events, transcripts)

    metadata: dict[str, str] = {}
    has_audio = bool(bucket.audio) or any(media.wav is not None for media in videos)
    if language != "en" and has_audio:
        metadata["language_limitation"] = (
            f"ASR is en-only; transcript may be unreliable for {language}"
        )
        warnings.append(metadata["language_limitation"])

    dossier = SourceDossier(
        id=new_id(),
        created_at=clock(),
        sha256=_hash_sources(sources),
        text_blocks=bucket.text_blocks,
        image_insights=image_insights,
        transcripts=transcripts,
        video_events=video_events,
        metadata=metadata,
    )
    return dossier, warnings


def _classify(sources: list[SourceInput]) -> _Bucket:
    """Split sources by modality; inline text and text files are extracted immediately."""
    bucket = _Bucket()
    for source in sources:
        if source.kind is SourceKind.text:
            bucket.text_blocks.append(TextBlock(source_name="inline", text=source.text or ""))
            continue
        path = Path(source.path or "")
        suffix = path.suffix.lower()
        if suffix in _TEXT:
            blocks, warns = extract_blocks(path)
            bucket.warnings.extend(warns)
            bucket.text_blocks.extend(blocks)
        elif suffix in _IMAGE:
            bucket.images.append(path)
        elif suffix in _AUDIO:
            bucket.audio.append(path)
        elif suffix in _VIDEO:
            bucket.videos.append(path)
        else:
            bucket.warnings.append(f"unsupported source type: {suffix or path.name}")
    return bucket


def _prepare_media(bucket: _Bucket, out_dir: Path, warnings: list[str]) -> list[_VideoMedia]:
    """Model-free ffmpeg pass: keyframes, an audio track and a duration for every video."""
    media: list[_VideoMedia] = []
    for video in bucket.videos:
        frames, frame_warns = keyframes(video, out_dir / video.stem)
        warnings.extend(frame_warns)
        wav, audio_warns = extract_audio(video, out_dir / f"{video.stem}.wav")
        warnings.extend(audio_warns)
        media.append(_VideoMedia(video.name, frames, wav, probe_duration(video)))
    return media


async def _run_vision(
    images: list[Path], videos: list[_VideoMedia], manager: ModelManager, warnings: list[str]
) -> tuple[list[ImageInsight], dict[str, list[tuple[float, str]]]]:
    """Acquire the VLM once, caption standalone images and every keyframe, then evict it."""
    if not images and not any(media.frames for media in videos):
        return [], {}
    insights: list[ImageInsight] = []
    captioned: dict[str, list[tuple[float, str]]] = {}
    async with manager.acquire("vlm") as lease:
        client = LlamaClient(lease.endpoint)
        try:
            for target in images:
                insight, warns = await caption_image(target, client)
                warnings.extend(warns)
                if insight is not None:
                    insights.append(insight)
            for media in videos:
                captioned[media.name] = await _caption_frames(media.frames, client, warnings)
        finally:
            await client.aclose()
    await manager.evict("vlm")
    return insights, captioned


async def _caption_frames(
    frames: list[Keyframe], client: LlamaClient, warnings: list[str]
) -> list[tuple[float, str]]:
    """Caption each keyframe of one video, keeping (timestamp, caption) pairs."""
    pairs: list[tuple[float, str]] = []
    for frame_path, timestamp in frames:
        insight, warns = await caption_image(frame_path, client)
        warnings.extend(warns)
        if insight is not None:
            pairs.append((timestamp, insight.caption))
    return pairs


async def _run_audio(
    audio: list[Path], videos: list[_VideoMedia], manager: ModelManager, warnings: list[str]
) -> tuple[list[Transcript], dict[str, list[TranscriptSegment]]]:
    """Acquire the ASR worker once, transcribe standalone audio and each video track, then evict."""
    if not audio and not any(media.wav is not None for media in videos):
        return [], {}
    transcripts: list[Transcript] = []
    video_segments: dict[str, list[TranscriptSegment]] = {}
    async with manager.acquire("asr") as lease:
        for target in audio:
            transcript, warns = await transcribe(target, lease.endpoint)
            warnings.extend(warns)
            if transcript is not None:
                transcripts.append(transcript)
        for media in videos:
            video_segments[media.name] = await _transcribe_video(media, lease.endpoint, warnings)
    await manager.evict("asr")
    return transcripts, video_segments


async def _transcribe_video(
    media: _VideoMedia, endpoint: str, warnings: list[str]
) -> list[TranscriptSegment]:
    """Transcribe one video's audio track into timed segments, or an empty list on failure."""
    if media.wav is None:
        return []
    transcript, warns = await transcribe(media.wav, endpoint)
    warnings.extend(warns)
    return transcript.segments if transcript is not None else []


def _build_video_events(
    video_name: str,
    captioned_frames: list[tuple[float, str]],
    segments: list[TranscriptSegment],
    total: float,
) -> list[VideoEvent]:
    """Group consecutive keyframe spans into VideoEvents with caption and overlapping speech."""
    frames = sorted(captioned_frames)
    events: list[VideoEvent] = []
    for index, (keyframe_time, caption) in enumerate(frames):
        start = 0.0 if index == 0 else keyframe_time
        end = frames[index + 1][0] if index + 1 < len(frames) else max(total, keyframe_time)
        spoken = " ".join(
            seg.text.strip() for seg in segments if seg.start < end and seg.end > start
        ).strip()
        events.append(
            VideoEvent(
                source_name=video_name, start=start, end=end, caption=caption, transcript=spoken
            )
        )
    return events


def _assign_evidence_ids(
    text_blocks: list[TextBlock],
    image_insights: list[ImageInsight],
    video_events: list[VideoEvent],
    transcripts: list[Transcript],
) -> None:
    """Assign E1, E2, ... across text blocks, images, video events, then transcript segments."""
    counter = 1
    for block in text_blocks:
        block.evidence_id = f"E{counter}"
        counter += 1
    for insight in image_insights:
        insight.evidence_id = f"E{counter}"
        counter += 1
    for event in video_events:
        event.evidence_id = f"E{counter}"
        counter += 1
    for transcript in transcripts:
        for segment in transcript.segments:
            segment.evidence_id = f"E{counter}"
            counter += 1


def _hash_sources(sources: list[SourceInput]) -> str:
    """SHA-256 over concatenated source bytes (file contents) and inline text, in order."""
    digest = hashlib.sha256()
    for source in sources:
        if source.kind is SourceKind.text:
            digest.update((source.text or "").encode("utf-8"))
        else:
            path = Path(source.path or "")
            try:
                digest.update(path.read_bytes())
            except OSError:
                digest.update(str(path).encode("utf-8"))
    return digest.hexdigest()
