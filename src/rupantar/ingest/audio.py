"""Audio transcription via a whisper (or stub) worker endpoint."""

from __future__ import annotations

from pathlib import Path

from rupantar.core.schemas import Transcript, TranscriptSegment


async def transcribe(audio_path: Path, endpoint: str) -> tuple[Transcript | None, list[str]]:
    """POST the audio path to `endpoint`/transcribe; return (transcript, warnings), never raise."""
    import httpx

    url = endpoint.rstrip("/") + "/transcribe"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0)) as client:
            response = await client.post(url, json={"audio_path": str(audio_path)})
            response.raise_for_status()
            data = response.json()
        segments = [
            TranscriptSegment(
                start=float(seg["start"]), end=float(seg["end"]), text=str(seg["text"])
            )
            for seg in data.get("segments", [])
        ]
        return Transcript(
            source_name=audio_path.name, text=str(data.get("text", "")), segments=segments
        ), []
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        return None, [f"transcription failed for {audio_path.name}: {type(exc).__name__}: {exc}"]
