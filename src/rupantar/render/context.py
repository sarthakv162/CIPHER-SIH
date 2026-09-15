"""RenderContext: optional extra material a renderer draws on. ``render_video`` uses the theme/
dossier/source-path/infographic/advisory-severity/video-style fields; ``render_pptx``/
``render_docx`` use ``template_id`` and ``configs_dir`` to select a document template, and
append to ``warnings`` on a template fallback so the caller can fold them into the artefact's
provenance manifest. Every other renderer ignores this object entirely.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rupantar.core.artefacts import InfographicSpec
from rupantar.core.schemas import SourceDossier, VideoStyle


@dataclass(frozen=True)
class RenderContext:
    """Theme name plus dossier/source material, and the selected document template."""

    theme_name: str = "ntro-formal"
    dossier: SourceDossier | None = None
    source_paths: list[Path] = field(default_factory=list)
    infographic_spec: InfographicSpec | None = None
    template_id: str = "ntro-formal"
    configs_dir: Path | None = None
    advisory_severity: str = ""
    video_style: VideoStyle = VideoStyle.composed
    # Mutated by render_pptx/render_docx when they degrade to a fallback; the frozen dataclass
    # only forbids reassigning this attribute, not appending to the list it already holds.
    warnings: list[str] = field(default_factory=list)
    # Populated by render_video, keyed by written filename (e.g. "panel_03.png"), with one of
    # "synthetic" / "b_roll" / "infographic"; read back by the caller for the file's manifest.
    panel_provenance: dict[str, str] = field(default_factory=dict)
