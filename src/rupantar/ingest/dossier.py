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
)
from rupantar.ingest.audio import transcribe
from rupantar.ingest.image import caption_image
from rupantar.ingest.text import text_block
from rupantar.ingest.video import extract_audio, keyframes
from rupantar.models.client import LlamaClient
from rupantar.models.manager import ModelManager

_TEXT = {".pdf", ".docx", ".html", ".htm", ".md", ".markdown", ".txt"}
_IMAGE = {".png", ".jpg", ".jpeg", ".webp"}
_AUDIO = {".wav", ".mp3", ".m4a", ".flac"}
_VIDEO = {".mp4", ".mov", ".mkv"}


@dataclass
class _Bucket:
    """Sources sorted by modality plus the artefacts of the model-free first pass."""

    text_blocks: list[TextBlock] = field(default_factory=list)
    images: list[Path] = field(default_factory=list)
    audio: list[Path] = field(default_factory=list)
    videos: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


async def assemble_dossier(
    sources: list[SourceInput],
    *,
    manager: ModelManager,
    out_dir: Path,
    new_id: Callable[[], str],
    clock: Callable[[], datetime],
    language: str = "en",
) -> tuple[SourceDossier, list[str]]:
    """Reduce every source to text, captioning images/keyframes then transcribing audio."""
    bucket = _classify(sources)
    warnings = bucket.warnings

    keyframe_targets, audio_targets = _prepare_media(bucket, out_dir, warnings)
    vision_targets = [*bucket.images, *keyframe_targets]

    image_insights = await _run_vision(vision_targets, manager, warnings)
    transcripts = await _run_audio(audio_targets, manager, warnings)

    metadata: dict[str, str] = {}
    if language != "en" and audio_targets:
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
            block, warns = text_block(path)
            bucket.warnings.extend(warns)
            if block is not None:
                bucket.text_blocks.append(block)
        elif suffix in _IMAGE:
            bucket.images.append(path)
        elif suffix in _AUDIO:
            bucket.audio.append(path)
        elif suffix in _VIDEO:
            bucket.videos.append(path)
        else:
            bucket.warnings.append(f"unsupported source type: {suffix or path.name}")
    return bucket


def _prepare_media(
    bucket: _Bucket, out_dir: Path, warnings: list[str]
) -> tuple[list[Path], list[Path]]:
    """Model-free ffmpeg pass: keyframes and audio tracks for every video source."""
    keyframe_targets: list[Path] = []
    audio_targets: list[Path] = list(bucket.audio)
    for video in bucket.videos:
        frames, frame_warns = keyframes(video, out_dir / video.stem)
        warnings.extend(frame_warns)
        keyframe_targets.extend(frames)
        wav, audio_warns = extract_audio(video, out_dir / f"{video.stem}.wav")
        warnings.extend(audio_warns)
        if wav is not None:
            audio_targets.append(wav)
    return keyframe_targets, audio_targets


async def _run_vision(
    targets: list[Path], manager: ModelManager, warnings: list[str]
) -> list[ImageInsight]:
    """Acquire the VLM, caption every target, then release and evict it."""
    if not targets:
        return []
    insights: list[ImageInsight] = []
    async with manager.acquire("vlm") as lease:
        client = LlamaClient(lease.endpoint)
        try:
            for target in targets:
                insight, warns = await caption_image(target, client)
                warnings.extend(warns)
                if insight is not None:
                    insights.append(insight)
        finally:
            await client.aclose()
    await manager.evict("vlm")
    return insights


async def _run_audio(
    targets: list[Path], manager: ModelManager, warnings: list[str]
) -> list[Transcript]:
    """Acquire the ASR worker, transcribe every target, then release and evict it."""
    if not targets:
        return []
    transcripts: list[Transcript] = []
    async with manager.acquire("asr") as lease:
        for target in targets:
            transcript, warns = await transcribe(target, lease.endpoint)
            warnings.extend(warns)
            if transcript is not None:
                transcripts.append(transcript)
    await manager.evict("asr")
    return transcripts


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
