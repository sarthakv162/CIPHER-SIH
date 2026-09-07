"""RenderContext: optional extra material the video renderer draws on. Only ``render_video``
consumes it; every other renderer ignores it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rupantar.core.artefacts import InfographicSpec
from rupantar.core.schemas import SourceDossier


@dataclass(frozen=True)
class RenderContext:
    """Theme name plus the dossier, original source paths, and an optional infographic spec."""

    theme_name: str = "ntro-formal"
    dossier: SourceDossier | None = None
    source_paths: list[Path] = field(default_factory=list)
    infographic_spec: InfographicSpec | None = None
