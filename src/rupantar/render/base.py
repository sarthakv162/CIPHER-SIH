"""Format dispatch: map an artefact to its renderers and write the files."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from rupantar.core.artefacts import ArtefactBase
from rupantar.core.errors import RenderError
from rupantar.render.context import RenderContext
from rupantar.render.docx_render import render_docx
from rupantar.render.markdown import render_md
from rupantar.render.pdf_render import render_pdf
from rupantar.render.pptx_render import render_pptx
from rupantar.render.subtitle import render_srt
from rupantar.render.svg_render import render_svg
from rupantar.render.video_render import render_video

FORMATS: dict[str, tuple[str, ...]] = {
    "executive_summary": ("md", "docx"),
    "advisory": ("md", "docx", "pdf"),
    "linkedin_post": ("md",),
    "x_thread": ("md",),
    "presentation": ("md", "pptx"),
    "infographic_spec": ("md", "svg"),
    "video_package": ("md", "srt", "video"),
}

_Renderer = Callable[[Any, Path], list[Path] | None]

_DISPATCH: dict[tuple[str, str], _Renderer] = {
    ("*", "md"): render_md,
    ("executive_summary", "docx"): render_docx,
    ("advisory", "docx"): render_docx,
    ("advisory", "pdf"): render_pdf,
    ("presentation", "pptx"): render_pptx,
    ("infographic_spec", "svg"): render_svg,
    ("video_package", "srt"): render_srt,
    ("video_package", "video"): render_video,
}


def _artefact_type(artefact: ArtefactBase) -> str:
    """The artefact_type discriminator string of a concrete artefact model."""
    return str(artefact.artefact_type)  # type: ignore[attr-defined]


def render(
    artefact: ArtefactBase,
    out_dir: Path,
    *,
    formats: Iterable[str] | None = None,
    context: RenderContext | None = None,
) -> list[Path]:
    """Render `artefact` to each requested format under `out_dir`; return the written paths.

    Only ``render_video`` consumes ``context``; every other renderer ignores it.
    """
    atype = _artefact_type(artefact)
    wanted = tuple(formats) if formats is not None else FORMATS.get(atype, ("md",))
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for fmt in wanted:
        renderer = _DISPATCH.get((atype, fmt)) or _DISPATCH.get(("*", fmt))
        if renderer is None:
            raise RenderError(
                f"no renderer for ({atype!r}, {fmt!r}); add one to render/base.py _DISPATCH "
                "or drop the format from FORMATS"
            )
        path = out_dir / f"{atype}.{fmt}"
        result: list[Path] | None = (
            render_video(artefact, path, context=context)
            if renderer is render_video
            else renderer(artefact, path)
        )
        written.extend(result or [path])
    return written
