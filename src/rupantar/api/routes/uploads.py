"""POST /sources: accept a source file from the console and return its path on disk.

The engine reads sources from the filesystem, and a browser never exposes a real path,
so the console had no way to supply a file at all. This takes the bytes directly as the
request body with the name in a query parameter -- deliberately not multipart, which
would pull `python-multipart` into an air-gapped dependency closure for no gain.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from rupantar.api.app import get_config
from rupantar.api.paths import safe_file_name
from rupantar.core.config import AppConfig

router = APIRouter(tags=["sources"])

# 512 MB: comfortably past a long video, far short of filling the demo laptop's disk.
MAX_BYTES = 512 * 1024 * 1024

# Only what `ingest/` can actually read. An extension outside this list would reach the
# dossier builder and be dropped with a warning, so refuse it here where we can say why.
ALLOWED_SUFFIXES = frozenset(
    {
        ".txt",
        ".md",
        ".html",
        ".htm",
        ".pdf",
        ".docx",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".gif",
        ".wav",
        ".mp3",
        ".m4a",
        ".flac",
        ".ogg",
        ".mp4",
        ".mov",
        ".mkv",
        ".webm",
    }
)

# Converter uploads have their own allowlist; these are not valid AI source files.
CONVERSION_SUFFIXES = frozenset(
    {
        ".csv",
        ".tsv",
        ".json",
        ".jsonl",
        ".yaml",
        ".yml",
        ".xml",
        ".xlsx",
        ".parquet",
        ".log",
        ".cef",
        ".txt",
    }
)


class UploadResult(BaseModel):
    """Where the file landed, ready to be used as a `SourceInput.path`."""

    path: str
    name: str
    size_bytes: int


def sanitise(name: str) -> str:
    """Reduce a browser-supplied filename to a safe single path segment, or "" if it cannot be."""
    # NFKD first: a composed character can normalise into a separator.
    cleaned = unicodedata.normalize("NFKD", name).strip().replace("\x00", "")
    cleaned = cleaned.replace("\\", "/").split("/")[-1]
    cleaned = "".join(ch for ch in cleaned if ch.isprintable() and ch not in '<>:"|?*')
    cleaned = cleaned.lstrip(".")[:180]
    return cleaned if safe_file_name(cleaned) else ""


def unique_path(directory: Path, name: str) -> Path:
    """A path inside `directory` that does not exist yet, suffixing -1, -2 ... on collision."""
    candidate = directory / name
    if not candidate.exists():
        return candidate
    stem, suffix = Path(name).stem, Path(name).suffix
    for index in range(1, 1000):
        candidate = directory / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
    raise HTTPException(status_code=409, detail=f"too many files named {name!r}")


@router.post("/sources", status_code=201)
async def upload_source(
    request: Request,
    config: Annotated[AppConfig, Depends(get_config)],
    filename: Annotated[str, Query(min_length=1, max_length=255)],
    purpose: Annotated[Literal["source", "conversion"], Query()] = "source",
) -> UploadResult:
    """Write an uploaded source under `data/uploads/` and return the path to transform."""
    name = sanitise(filename)
    if not name:
        raise HTTPException(status_code=400, detail="filename is not a usable file name")
    suffix = Path(name).suffix.lower()
    allowed = CONVERSION_SUFFIXES if purpose == "conversion" else ALLOWED_SUFFIXES
    if suffix not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"{suffix or 'that file type'} is not supported for {purpose} uploads",
        )

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="empty upload")
    if len(body) > MAX_BYTES:
        raise HTTPException(
            status_code=413, detail=f"file exceeds the {MAX_BYTES // (1024 * 1024)} MB limit"
        )

    directory = (config.db_path.parent / "uploads").resolve()
    directory.mkdir(parents=True, exist_ok=True)
    target = unique_path(directory, name)

    # Belt and braces: the name is already validated, but assert containment on the
    # resolved path too, exactly as the download route does.
    if target.resolve().parent != directory:
        raise HTTPException(status_code=400, detail="refusing a path outside the upload directory")

    target.write_bytes(body)
    return UploadResult(path=str(target), name=target.name, size_bytes=len(body))
