"""Convert routes: list conversion pairs, run one file conversion, and serve its output."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from rupantar.api.app import get_config
from rupantar.api.paths import resolve_job_file
from rupantar.api.routes.files import content_type_for
from rupantar.core.config import AppConfig
from rupantar.core.errors import ConversionError
from rupantar.parivartan.registry import convert, list_conversions

router = APIRouter(tags=["convert"])

_FORMAT_TO_EXT: dict[str, str] = {
    "stix21": "json",
    "sigma-json": "json",
    "ioc-csv": "csv",
    "cef": "jsonl",
}


class ConvertRequest(BaseModel):
    """Body for POST /convert: a file already on disk plus source and destination formats."""

    input_path: str
    src_format: str
    dst_format: str
    opts: dict[str, Any] = {}


class ConvertResponse(BaseModel):
    """The ConversionReport as JSON, plus the file name to download it by."""

    src_format: str
    dst_format: str
    rows: int
    warnings: list[str]
    output_path: str | None
    download_name: str | None
    duration_seconds: float
    ok: bool


@router.get("/conversions")
async def conversions() -> list[dict[str, str]]:
    """Every available (src, dst) conversion pair with its label and notes."""
    return list_conversions()


@router.post("/convert")
async def run_conversion(
    body: ConvertRequest,
    config: Annotated[AppConfig, Depends(get_config)],
) -> ConvertResponse:
    """Convert a file and return its ConversionReport; unknown format pair -> 400."""
    source = Path(body.input_path)
    ext = _FORMAT_TO_EXT.get(body.dst_format, body.dst_format)
    out_path = config.db_path.parent / "outputs" / "conversions" / f"{source.stem}.{ext}"
    try:
        report = convert(source, body.src_format, body.dst_format, out_path, body.opts)
    except ConversionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    download_name = Path(report.output_path).name if report.output_path else None
    return ConvertResponse(**asdict(report), download_name=download_name)


@router.get("/conversions/download/{filename}")
async def download_conversion(
    filename: str,
    config: Annotated[AppConfig, Depends(get_config)],
) -> FileResponse:
    """Serve one converted file by name; anything outside the conversions directory is a 404."""
    conversions_dir = config.db_path.parent / "outputs" / "conversions"
    path = resolve_job_file(conversions_dir, filename)
    if path is None:
        raise HTTPException(status_code=404, detail=f"no converted file {filename!r}")
    return FileResponse(
        path,
        media_type=content_type_for(path.name),
        headers={"content-disposition": f"attachment; filename*=UTF-8''{quote(path.name)}"},
    )
