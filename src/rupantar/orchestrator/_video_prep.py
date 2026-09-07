"""Video-job render prep: collect source file paths and, when a video job did not request an
infographic spec, generate one internally inside the open brain lease (one extra generation
call, no new model, not persisted or manifested).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from rupantar.core.artefacts import InfographicSpec
from rupantar.core.errors import AgentError
from rupantar.core.schemas import ArtefactType, Job, SourceInput, SourceKind
from rupantar.models.client import LlamaClient

if TYPE_CHECKING:  # pragma: no cover - typing only
    from rupantar.orchestrator.runner import _RunContext


def file_source_paths(sources: list[SourceInput]) -> list[Path]:
    """The on-disk paths of every file source in the request (for b-roll backgrounds)."""
    return [Path(s.path) for s in sources if s.kind is SourceKind.file and s.path]


async def ensure_infographic_spec(group: list[Job], ctx: _RunContext, client: LlamaClient) -> None:
    """Populate ``ctx.infographic_holder['spec']`` for a video job that lacks an infographic.

    An ``AgentError`` is swallowed: the video simply gets no hero panel.
    """
    if "spec" in ctx.infographic_holder:
        return
    types = {job.artefact_type for job in group}
    if ArtefactType.video_package not in types or ArtefactType.infographic_spec in types:
        return
    agent = ctx.agents.get("infographic_spec")
    if agent is None:
        return
    try:
        spec: Any = await agent.run(ctx.dossier_text, ctx.request.params, client, stream=ctx.stream)
    except AgentError:
        return
    if isinstance(spec, InfographicSpec):
        ctx.infographic_holder["spec"] = spec
