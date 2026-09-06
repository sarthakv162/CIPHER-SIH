"""Scheduler: order jobs by modality so a batch causes one model swap per modality."""

from __future__ import annotations

from rupantar.core.schemas import Job

# The PLAN.md §4 pipeline: images are captioned (vlm) and audio transcribed (asr) before
# the brain agents read the assembled dossier. This is a data dependency, not cosmetics.
_MODALITY_PRIORITY: dict[str, int] = {"vlm": 0, "asr": 1, "brain": 2}
_UNKNOWN_RANK = 3


def _rank(model_key: str) -> tuple[int, str]:
    """Sort key: known modalities in pipeline order, unknown keys last and alphabetical."""
    if model_key in _MODALITY_PRIORITY:
        return (_MODALITY_PRIORITY[model_key], "")
    return (_UNKNOWN_RANK, model_key)


def schedule(jobs: list[Job]) -> list[Job]:
    """Group jobs by model modality (stable within a group), then honour depends_on edges."""
    grouped = sorted(jobs, key=lambda job: _rank(job.model_key))
    return _topological(grouped)


def _topological(grouped: list[Job]) -> list[Job]:
    """Stably emit jobs so none precedes a job listed in its depends_on."""
    emitted: list[Job] = []
    emitted_ids: set[str] = set()
    remaining = list(grouped)
    while remaining:
        for index, job in enumerate(remaining):
            if all(dep in emitted_ids for dep in job.depends_on):
                emitted.append(job)
                emitted_ids.add(job.id)
                del remaining[index]
                break
        else:
            emitted.extend(remaining)
            break
    return emitted
